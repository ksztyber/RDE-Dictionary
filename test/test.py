#! /usr/bin/python3
# Copyright Notice:
# Copyright 2018-2019 DMTF. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/RDE-Dictionary/blob/master/LICENSE.md

import json
import os
import re
import io
from collections import namedtuple
import importlib
import sys
import argparse
from utils import *
import shutil
import stat
import traceback
import requests
import zipfile

sys.path.append('./')

from rdebej import dictionary
from rdebej import encode, decode


COPYRIGHT = 'Copyright (c) 2018 DMTF'

TestSpecification = namedtuple('TestSpecification', 'csdl_directories '
                                                    'json_schema_directories '
                                                    'schema_filename '
                                                    'entity '
                                                    'oem_schema_filenames '
                                                    'oem_entities '
                                                    'profile '
                                                    'dictionary_filename '
                                                    'input_encode_filename '
                                                    'copyright')
MAJOR_SCHEMA_DICTIONARY_LIST = [
                                TestSpecification(
                                    'test/schema/dummysimple/csdl',
                                    'test/schema/dummysimple/json-schema',
                                    'DummySimple_v1.xml',
                                    'DummySimple.DummySimple',
                                    '',
                                    '',
                                    '',
                                    'DummySimple.bin',
                                    'test/dummysimple.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    'test/schema/dummysimple/csdl',
                                    'test/schema/dummysimple/json-schema',
                                    'DummySimple_v1.xml',
                                    'DummySimple.DummySimple',
                                    '',
                                    '',
                                    '',
                                    'DummySimple.bin',
                                    'test/dummysimple2.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    '$csdl_dir test/schema/oem-csdl',
                                    '$json_schema_dir',
                                    'Drive_v1.xml',
                                    'Drive.Drive',
                                    'OEM1DriveExt_v1.xml OEM2DriveExt_v1.xml',
                                    'OEM1=OEM1DriveExt.OEM1DriveExt OEM2=OEM2DriveExt.OEM2DriveExt',
                                    '',                # profile
                                    'drive.bin',
                                    'test/drive.json',      # file to encode
                                    'Copyright (c) 2018 Acme Corp'),  # encoded bej file

                                TestSpecification(
                                    '$csdl_dir',
                                    '$json_schema_dir',
                                    'Storage_v1.xml',
                                    'Storage.Storage',
                                    '',
                                    '',
                                    '',
                                    'storage.bin',
                                    'test/storage.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    '$csdl_dir',
                                    '$json_schema_dir',
                                    'Storage_v1.xml',
                                    'Storage.Storage',
                                    '',
                                    '',
                                    '',
                                    'storage.bin',
                                    'test/storage_large.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    '$csdl_dir',
                                    '$json_schema_dir',
                                    'Outlet_v1.xml',
                                    'Outlet.Outlet',
                                    '',
                                    '',
                                    '',
                                    'outlet.bin',
                                    'test/outlet.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    '$csdl_dir',
                                    '$json_schema_dir',
                                    'Circuit_v1.xml',
                                    'Circuit.Circuit',
                                    '',
                                    '',
                                    '',
                                    'circuit.bin',
                                    'test/circuit.json',
                                    'Copyright (c) 2018 Acme Corp'),

                                TestSpecification(
                                    '$csdl_dir',
                                    '$json_schema_dir',
                                    'Storage_v1.xml',
                                    'Storage.Storage',
                                    '',
                                    '',
                                    'test/example_profile_for_truncation.json',
                                    'storage.bin',
                                    'test/storage_profile_conformant.json',
                                    'Copyright (c) 2018 Acme Corp')
                                ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--test_bej", help="test only BEJ", action="store_true")
    parser.add_argument("--schema_source", help="source for schema files", type=str, required=True)
    parser.add_argument("--git_tag", help="git repo tag", type=str, required=False)
    parser.add_argument("--delete_schema_dir", help="cleanup the schema directories", action="store_true")
    parser.add_argument("--save_dictionaries", help="location to store dictionaries", type=str, required=False)

    args = parser.parse_args()

    # default location of schema files
    schema_test_dir = 'test/schema'
    delete_schema_test_dir = False

    if args.schema_source:
        # we support only git repos from the master branch
        if re.search('.*\.git$', args.schema_source):
            schema_test_dir = 'tmp-schema'
            branch = 'master'
            if args.git_tag:
                branch = args.git_tag
            repo = cloneFrom(args.schema_source, schema_test_dir, branch, ['metadata', 'json-schema'])
            if not repo:
                exit(1)
        elif re.search('https://.*\.zip$', args.schema_source):
            schema_test_dir = 'tmp-schema'
            r = requests.get(args.schema_source, allow_redirects=True)
            open('tmp_schema.zip', 'wb').write(r.content)
            with zipfile.ZipFile('tmp_schema.zip', 'r') as zip_ref:
                zip_ref.extractall('tmp-schema')
                schema_test_dir = 'tmp-schema/'+os.listdir('tmp-schema')[0]
        else: # standard directory
            schema_test_dir = args.schema_source

    if args.delete_schema_dir:
        delete_schema_test_dir = True

    csdl_dir = schema_test_dir + '/metadata'
    json_schema_dir = schema_test_dir + '/json-schema'
    if os.path.isdir(schema_test_dir + '/metadata'):
        csdl_dir = schema_test_dir + '/metadata'
    elif os.path.isdir(schema_test_dir + '/csdl'):
        csdl_dir = schema_test_dir + '/csdl'

    if not args.test_bej:
        # go thru every csdl and attempt creating a dictionary
        skip_list = []

        for filename in os.listdir(csdl_dir):
            if filename not in skip_list:
                # strip out the _v1.xml
                m = re.compile('(.*)_v1.xml').match(filename)
                entity = ''
                if m:
                    entity = m.group(1) + '.' + m.group(1)

                try:
                    schema_dictionary = dictionary.generate_schema_dictionary(
                        'local',
                        [csdl_dir],
                        [json_schema_dir],
                        entity,
                        filename,
                        None,
                        None,
                        None,
                        None,
                        COPYRIGHT
                    )

                    if schema_dictionary and schema_dictionary.dictionary and schema_dictionary.json_dictionary:
                        print(filename, 'Entries:', len(schema_dictionary.dictionary),
                              'Size:', len(schema_dictionary.dictionary_byte_array),
                              'Url:', json.loads(schema_dictionary.json_dictionary)['schema_url'])
                        # verify copyright
                        assert(bytearray(schema_dictionary.dictionary_byte_array[
                                         len(schema_dictionary.dictionary_byte_array) - len(COPYRIGHT) - 1:
                                         len(schema_dictionary.dictionary_byte_array)-1]).decode('utf-8') == COPYRIGHT)
                        if args.save_dictionaries:
                            dir_to_save = args.save_dictionaries
                            if not os.path.exists(dir_to_save):
                                os.makedirs(dir_to_save)

                            # save the binary and also dump the ascii version
                            with open(dir_to_save + '//' + filename.replace('.xml', '.dict'), 'wb') as file:
                                file.write(bytes(schema_dictionary.dictionary_byte_array))

                    else:
                        print(filename, "Missing entities, skipping...")

                except Exception as ex:
                    print("Error: Could not generate JSON schema dictionary for schema:", filename)
                    print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
                    exit(1)

    # Generate the annotation dictionary
    print('Generating annotation dictionary...')
    annotation_dictionary = None
    try:
        annotation_dictionary = dictionary.generate_annotation_schema_dictionary(
            [csdl_dir],
            [json_schema_dir],
            'v1_0_0'
        )

        if annotation_dictionary and annotation_dictionary.dictionary \
                and annotation_dictionary.dictionary_byte_array and annotation_dictionary.json_dictionary:
            print('Entries:', len(annotation_dictionary.dictionary), 'Size:',
                  len(annotation_dictionary.dictionary_byte_array))

            dir_to_save = './'
            if args.save_dictionaries:
                dir_to_save = args.save_dictionaries

            with open(dir_to_save + '//' + 'annotation.dict', 'wb') as annotaton_bin:
                annotaton_bin.write(bytearray(annotation_dictionary.dictionary_byte_array))
            dictionary.print_binary_dictionary(annotation_dictionary.dictionary_byte_array)

    except Exception as ex:
        print("Error: Could not generate JSON schema dictionary for schema annotation")
        print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
        exit(1)

    # Generate the error schema dictionary
    print('Generating error schema dictionary...')
    error_schema_dictionary = None
    try:
        error_schema_dictionary = dictionary.generate_error_schema_dictionary(
            [csdl_dir],
            [json_schema_dir]
        )

        if error_schema_dictionary and error_schema_dictionary.dictionary \
                and error_schema_dictionary.dictionary_byte_array and error_schema_dictionary.json_dictionary:
            print('Entries:', len(error_schema_dictionary.dictionary), 'Size:',
                  len(error_schema_dictionary.dictionary_byte_array))

            dir_to_save = './'
            if args.save_dictionaries:
                dir_to_save = args.save_dictionaries

            with open(dir_to_save + '//' + 'error.dict', 'wb') as error_bin:
                error_bin.write(bytearray(error_schema_dictionary.dictionary_byte_array))
            dictionary.print_binary_dictionary(error_schema_dictionary.dictionary_byte_array)

        # Run the encode/decode
        bej_stream = io.BytesIO()

        json_to_encode = json.load(open('test/error.json'))
        encode_success, pdr_map = encode.bej_encode(
                                        bej_stream,
                                        json_to_encode,
                                        error_schema_dictionary.dictionary_byte_array,
                                        annotation_dictionary.dictionary_byte_array,
                                        verbose=True
                                    )
        assert encode_success,'Encode failure'
        encoded_bytes = bej_stream.getvalue()
        encode.print_encode_summary(json_to_encode, encoded_bytes)

        decode_stream = io.StringIO()
        decode_success = decode.bej_decode(
                                        decode_stream,
                                        io.BytesIO(bytes(encoded_bytes)),
                                        error_schema_dictionary.dictionary_byte_array,
                                        annotation_dictionary.dictionary_byte_array,
                                        error_schema_dictionary, pdr_map, {}
                                    )
        assert decode_success,'Decode failure'

        decode_file = decode_stream.getvalue()

        # compare the decode with the original
        print('Decoded JSON:')
        print(json.dumps(json.loads(decode_file), indent=3))
        assert(json.loads(decode_file) == json.load(open('test/error.json'))), \
            'Mismtach in original JSON and decoded JSON'

    except Exception as ex:
        print("Error: Could not validate error schema dictionary")
        print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
        traceback.print_exc()
        exit(1)

    # Generate the major schema dictionaries
    for major_schema in MAJOR_SCHEMA_DICTIONARY_LIST:
        schema_dictionary = None
        try:
            csdl_dirs = major_schema.csdl_directories.replace('$csdl_dir', csdl_dir)
            json_schema__dirs = major_schema.json_schema_directories.replace('$json_schema_dir', json_schema_dir)

            print(csdl_dirs)
            schema_dictionary = dictionary.generate_schema_dictionary(
                'local',
                csdl_dirs.split(),
                json_schema__dirs.split(),
                major_schema.entity,
                major_schema.schema_filename,
                major_schema.oem_entities.split(),
                major_schema.oem_schema_filenames.split(),
                major_schema.profile
            )

            if schema_dictionary and schema_dictionary.dictionary and schema_dictionary.json_dictionary:
                print('Entries:', len(schema_dictionary.dictionary), 'Size:',
                      len(schema_dictionary.dictionary_byte_array))
                with open(major_schema.dictionary_filename, 'wb') as dictionary_bin:
                    dictionary_bin.write(bytearray(schema_dictionary.dictionary_byte_array))
                dictionary.print_binary_dictionary(schema_dictionary.dictionary_byte_array)

        except Exception as ex:
            print("Error: Could not generate JSON schema dictionary for schema:", major_schema.schema_filename)
            print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
            exit(1)

        # Run the encode/decode
        bej_stream = io.BytesIO()

        json_to_encode = json.load(open(major_schema.input_encode_filename))
        encode_success, pdr_map = encode.bej_encode(
                                        bej_stream,
                                        json_to_encode,
                                        schema_dictionary.dictionary_byte_array,
                                        annotation_dictionary.dictionary_byte_array, True
                                    )

        # build the deferred binding strings from the pdr_map
        deferred_binding_strings = {}
        for url, pdr_num in pdr_map.items():
            deferred_binding_strings['%L' + str(pdr_num)] = url

        assert encode_success, 'Encode failure'
        encoded_bytes = bej_stream.getvalue()
        encode.print_encode_summary(json_to_encode, encoded_bytes)

        decode_stream = io.StringIO()
        decode_success = decode.bej_decode(
                                        decode_stream,
                                        io.BytesIO(bytes(encoded_bytes)),
                                        schema_dictionary.dictionary_byte_array,
                                        annotation_dictionary.dictionary_byte_array,
                                        error_schema_dictionary, pdr_map, deferred_binding_strings
                                    )
        assert decode_success, 'Decode failure'

        decode_file = decode_stream.getvalue()

        # compare the decode with the original
        print('Decoded JSON:')
        print(json.dumps(json.loads(decode_file), indent=3))
        assert(json.loads(decode_file) == json.load(open(major_schema.input_encode_filename)))

        # cleanup
        os.remove(major_schema.dictionary_filename)

    # cleanup
    if delete_schema_test_dir:
        shutil.rmtree(schema_test_dir, onerror=onerror)

    if not args.save_dictionaries:
        os.remove('annotation.dict')
        os.remove('error.dict')

    exit(code=0)
