#!/usr/bin/env python
import os
import sys
import subprocess
import argparse
import pkg_resources
import circus
import tempfile
import numpy, h5py
from circus.shared.messages import print_error, print_and_log, get_colored_header
from circus.shared.files import write_datasets
from circus.shared.parser import CircusParser

def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    header = get_colored_header()
    parser = argparse.ArgumentParser(description=header,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('datafile', help='data file')
    parser.add_argument('-e', '--extension', help='extension to consider for visualization',
                        default='')

    if len(argv) == 0:
        parser.print_help()
        sys.exit()

    args = parser.parse_args(argv)

    filename       = os.path.abspath(args.datafile)
    extension      = args.extension
    params         = CircusParser(filename)
    data_file      = params.get_data_file()
    data_dtype     = data_file.data_dtype
    gain           = 1
    file_out_suff  = params.get('data', 'file_out_suff')
    if hasattr(data_file, 'data_offset'):
        data_offset = data_file.data_offset
    else:
        data_offset = 0
    probe          = params.probe
    if extension != '':
        extension = '-' + extension

    def generate_matlab_mapping(probe):
        p         = {}
        positions = []
        nodes     = []
        for key in probe['channel_groups'].keys():
            p.update(probe['channel_groups'][key]['geometry'])
            nodes     +=  probe['channel_groups'][key]['channels']
            positions += [p[channel] for channel in probe['channel_groups'][key]['channels']]
        idx       = numpy.argsort(nodes)
        positions = numpy.array(positions)[idx]
            
        t     = tempfile.NamedTemporaryFile().name + '.hdf5'
        cfile = h5py.File(t, 'w')
        to_write = {'positions' : positions/10., 'permutation' : numpy.sort(nodes), 'nb_total' : numpy.array([probe['total_nb_channels']])}
        write_datasets(cfile, to_write.keys(), to_write) 
        cfile.close()
        return t

    mapping    = generate_matlab_mapping(probe)
    filename   = params.get('data', 'data_file')

    gui_params = [data_file.rate, os.path.abspath(file_out_suff), '%s.mat' %extension, mapping, 2, data_dtype, data_offset, gain, filename]

    gui_file = pkg_resources.resource_filename('circus', os.path.join('matlab_GUI', 'SortingGUI.m'))
    # Change to the directory of the matlab file
    os.chdir(os.path.abspath(os.path.dirname(gui_file)))

    # Use quotation marks for string arguments
    is_string = [False, True, True, True, False, True, False, False, True]
    arguments = ', '.join(["'%s'" % arg if s else "%s" % arg
                           for arg, s in zip(gui_params, is_string)])
    matlab_command = 'SortingGUI(%s)' % arguments

    print_and_log(["Launching the MATLAB GUI..."], 'info', params)

    try:
        sys.exit(subprocess.call(['matlab',
                              '-nodesktop',
                              '-nosplash',
                              '-r', matlab_command]))
    except Exception:
        print_error(["Something wrong with MATLAB. Try circus-gui-python instead?"])

if __name__ == '__main__':
    main()