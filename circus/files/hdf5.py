import h5py, numpy, re, sys
import ConfigParser as configparser
from circus.shared.messages import print_error, print_and_log
from datafile import DataFile

class H5File(DataFile):

    _description = "hdf5"    
    _parrallel_write = h5py.get_config().mpi

    def __init__(self, file_name, params, empty=False, comm=None):

        DataFile.__init__(self, file_name, params, empty, comm)
        self.h5_key      = self.params.get('data', 'hdf5_key_data')
        self.compression = 'gzip'
        if not self.empty:
            self._get_info_()

    def _get_info_(self):
        self.empty = False
        self.open()
        self.data_dtype  = self.my_file.get(self.h5_key).dtype
        self.compression = self.my_file.get(self.h5_key).compression

        # HDF5 does not support parallel writes with compression
        if self.compression != '':
        	self._parrallel_write = False
        
        self.size        = self.my_file.get(self.h5_key).shape
        self.set_dtype_offset(self.data_dtype)
        
        assert (self.size[0] == self.N_tot) or (self.size[1] == self.N_tot)
        if self.size[0] == self.N_tot:
            self.time_axis = 1
            self._shape = (self.size[1], self.size[0])
        else:
            self.time_axis = 0
            self._shape = self.size

        self.max_offset = self._shape[0]
        self.data_offset = 0
        self.close()

    def allocate(self, shape, data_dtype=None):

        if data_dtype is None:
            data_dtype = self.data_dtype

        if self._parrallel_write and (self.comm is not None):
            self.my_file = h5py.File(self.file_name, mode='w', driver='mpio', comm=self.comm)
            self.my_file.create_dataset(self.h5_key, dtype=data_dtype, shape=shape)
        else:
            self.my_file = h5py.File(self.file_name, mode='w')
            if self.is_master:
                if self.compression != '':
                    self.my_file.create_dataset(self.h5_key, dtype=data_dtype, shape=shape, compression=self.compression, chunks=True)
                else:
                    self.my_file.create_dataset(self.h5_key, dtype=data_dtype, shape=shape, chunks=True)

        self.my_file.close()
        self._get_info_()

    def get_data(self, idx, chunk_len, chunk_size=None, padding=(0, 0), nodes=None):

        if chunk_size is None:
            chunk_size = self.params.getint('data', 'chunk_size')

        if self.time_axis == 0:
            local_chunk = self.data[idx*numpy.int64(chunk_len)+padding[0]:(idx+1)*numpy.int64(chunk_len)+padding[1], :]
        elif self.time_axis == 1:
            local_chunk = self.data[:, idx*numpy.int64(chunk_len)+padding[0]:(idx+1)*numpy.int64(chunk_len)+padding[1]].T

        local_chunk  = local_chunk.astype(numpy.float32)
        local_chunk -= self.dtype_offset

        if nodes is not None:
            if not numpy.all(nodes == numpy.arange(self.N_tot)):
                local_chunk = numpy.take(local_chunk, nodes, axis=1)

        return numpy.ascontiguousarray(local_chunk), len(local_chunk)

    def get_snippet(self, time, length, nodes=None):

        if self.time_axis == 0:
            local_chunk = self.data[time:time+length, :]
        elif self.time_axis == 1:
            local_chunk = self.data[:, time:time+length].T

        local_chunk  = local_chunk.astype(numpy.float32)
        local_chunk -= self.dtype_offset

        if nodes is not None:
            if not numpy.all(nodes == numpy.arange(self.N_tot)):
                local_chunk = numpy.take(local_chunk, nodes, axis=1)
        
        return numpy.ascontiguousarray(local_chunk)


    def set_data(self, time, data):
        
    	data += self.dtype_offset
    	data  = data.astype(self.data_dtype)

        if self.time_axis == 0:
            local_chunk = self.data[time:time+data.shape[0], :] = data
        elif self.time_axis == 1:
            local_chunk = self.data[:, time:time+data.shape[0]] = data.T

    def analyze(self, chunk_size=None):

        if chunk_size is None:
            chunk_size = self.params.getint('data', 'chunk_size')
	    
        nb_chunks      = numpy.int64(self.shape[0]) // chunk_size
        last_chunk_len = self.shape[0] - nb_chunks * chunk_size

        if last_chunk_len > 0:
            nb_chunks += 1
        return nb_chunks, last_chunk_len

    def open(self, mode='r'):
        if self._parrallel_write and (self.comm is not None):
            self.my_file = h5py.File(self.file_name, mode=mode, driver='mpio', comm=self.comm)
        else:
            self.my_file = h5py.File(self.file_name, mode=mode)

        self.data = self.my_file.get(self.h5_key)
        
    def close(self):
        self.my_file.close()