#! /usr/bin/python3
# Copyright Notice:
# Copyright 2018-2019 DMTF. All rights reserved.
# License: BSD 3-Clause License. For full text see link: https://github.com/DMTF/RDE-Dictionary/blob/master/LICENSE.md

import sys
import os
import json
import re
import argparse

sys.path.append('./')

from rdebej import dictionary


def write_map_file(filename, schema_dictionary):
    with open(filename, 'w') as file:
        sys.stdout = file
        dictionary.print_table_data(
            [["Row", "Sequence#", "Format", "Flags", "Field String", "Child Count", "Offset"]]
            +
            schema_dictionary.dictionary)

        dictionary.print_dictionary_summary(schema_dictionary.dictionary,
                                            schema_dictionary.dictionary_byte_array)
        sys.stdout = sys.__stdout__


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csdl", help="source for local CSDL schema files", nargs='+',
                        required=True)
    parser.add_argument("--input-json-schema", help="source for local JSON schema files", nargs='+',
                        required=False)
    parser.add_argument("--config", help="config file for specific user options", required=False)

    parser.add_argument("--output", help="The folder(s) to write the RDE dictionary files", nargs='+', required=True)

    args = parser.parse_args()

    schema_dir_csdl = []
    schema_dir_json = []

    for source in args.input_csdl:
        schema_dir_csdl.append(source)

    if args.input_json_schema:
        for source in args.input_json_schema:
            schema_dir_json.append(source)

    copyright = ''
    do_not_write = []
    # Read the configuration file
    config_data = {}
    if args.config is not None:
        try:
            with open(args.config) as config_file:
                config_data = json.load(config_file)
                if 'Copyright' in config_data:
                    copyright = config_data['Copyright']
                if 'DoNotWrite' in config_data:
                    do_not_write = config_data['DoNotWrite']
        except json.JSONDecodeError:
            print("ERROR: {} contains a malformed JSON object".format(args.config))
            sys.exit(1)
        except:
            print("ERROR: Could not open {}".format(args.config))
            sys.exit(1)

    for i in range(0, len(schema_dir_csdl)):
        for filename in os.listdir(schema_dir_csdl[i]):
            if filename not in do_not_write:
                # strip out the _v1.xml
                m = re.compile('(.*)_v1.xml').match(filename)
                entity = ''
                if m:
                    entity = m.group(1) + '.' + m.group(1)

                try:
                    schema_dictionary = dictionary.generate_schema_dictionary(
                        'local',
                        schema_dir_csdl,
                        schema_dir_json,
                        entity,
                        filename,
                        None,
                        None,
                        None,
                        None,
                        copyright
                    )

                    if schema_dictionary and schema_dictionary.dictionary and schema_dictionary.json_dictionary:
                        print(filename, 'Entries:', len(schema_dictionary.dictionary),
                              'Size:', len(schema_dictionary.dictionary_byte_array),
                              'Url:', json.loads(schema_dictionary.json_dictionary)['schema_url'])

                        dir_to_save = args.output[i]

                        if not os.path.exists(dir_to_save):
                            os.makedirs(dir_to_save)

                        # save the binary and also dump the ascii version
                        with open(dir_to_save + '//' + filename.replace('.xml', '.bin'), 'wb') as file:
                            file.write(bytes(schema_dictionary.dictionary_byte_array))

                        write_map_file(dir_to_save + '//' + filename.replace('.xml', '.map'), schema_dictionary)
                    else:
                        print(filename, "Missing entities, skipping...")

                except Exception as ex:
                    print("Error: Could not generate RDE dictionary for schema:", filename)
                    print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
                    sys.exit(1)

    # Generate the annotation dictionary
    print('Generating annotation dictionary...')
    annotation_dictionary = None
    try:
        annotation_dictionary = dictionary.generate_annotation_schema_dictionary(
            schema_dir_csdl,
            schema_dir_json,
            'v1_0_0'
        )

        if annotation_dictionary and annotation_dictionary.dictionary \
                and annotation_dictionary.dictionary_byte_array and annotation_dictionary.json_dictionary:
            print('Entries:', len(annotation_dictionary.dictionary), 'Size:',
                  len(annotation_dictionary.dictionary_byte_array))

            dir_to_save = args.output[i]

            with open(dir_to_save + '//' + 'annotation.bin', 'wb') as annotaton_bin:
                annotaton_bin.write(bytearray(annotation_dictionary.dictionary_byte_array))

            write_map_file(dir_to_save + '//' + 'annotation.map', annotation_dictionary)

    except Exception as ex:
        print("Error: Could not generate Annotation RDE dictionary for schema: annotation.bin")
        print("Error: Exception type: {0}, message: {1}".format(ex.__class__.__name__, str(ex)))
        sys.exit(1)

    sys.exit(0)
