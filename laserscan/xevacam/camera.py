'''
Created on 9.11.2016

@author: Samuli Rahkonen
'''

import numpy as np
import laserscan.xevacam.xevadll as xdll
from contextlib import contextmanager
import threading
import queue
import sys
import time
import struct
import laserscan.xevacam.utils as utils
from laserscan.xevacam.utils import kbinterrupt_decorate

'''
class ExceptionThread(threading.Thread):


    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.exc_queue = queue.Queue()
'''


class XevaCam(object):

    def __init__(self, calibration=''):
        '''
        Constructor

        @param calibration: Bytes string path to the calibration file (.xca)
        '''
        self.handle = 0
        self.calibration = calibration.encode('utf-8')  # Path to .xca file

        # Involve threading
        self._enabled = False
        self.enabled_lock = threading.Lock()
        self.handlers = []  # For streams, objects with write() method
        # Exception queue for checking if an exception occurred inside thread
        self.exc_queue = queue.Queue()
        self._capture_thread = threading.Thread(name='capture_thread',
                                                target=self.capture_frame_stream)
                                        # args=(self.handlers))
        self._record_time = 0  # Used for measuring the overall recording time
        self._times = []  # Used for saving time stamps for each frame


    def open(self, camera_path='cam://0', sw_correction=True):
        '''
        Opens connection to the camera.
        '''
        # Existing implementation
        pass

    def start_capture(self, camera_path='cam://0', sw_correction=True):
        '''
        Starts the camera once, keeping it ready for capturing.
        '''
        self.handle = xdll.XDLL.open_camera(camera_path.encode('utf-8'), 0, 0)
        if self.handle == 0:
            raise Exception('Camera handle is NULL. Initialization failed.')
        if not xdll.XDLL.is_initialised(self.handle):
            raise Exception('Camera initialization failed.')
        if self.calibration:
            flag = xdll.XDLL.XLC_StartSoftwareCorrection if sw_correction else 0
            error = xdll.XDLL.load_calibration(self.handle, self.calibration, flag)
            if error != xdll.XDLL.I_OK:
                raise Exception(f'Calibration load failed: {xdll.error2str(error)}')
        print('Camera started and initialized successfully.')

    def capture_single_frame(self, dump_buffer=False):
        '''
        Captures a single frame (existing implementation).
        '''
        # Existing implementation
        pass

    def capture_frame_only(self):
        '''
        Captures a single frame without reinitializing the camera.
        '''
        name = 'capture_frame_only'
        frame_buffer = None

        if not xdll.XDLL.is_capturing(self.handle):
            error = xdll.XDLL.start_capture(self.handle)
            if error != xdll.XDLL.I_OK:
                raise Exception(f'{name}: Starting capture failed: {xdll.error2str(error)}')

        size = self.get_frame_size()
        dims = self.get_frame_dims()
        frame_t = self.get_frame_type()
        frame_buffer = bytes(size)

        ok = self.get_frame(
            frame_buffer,
            frame_t=frame_t,
            size=size,
            flag=xdll.XDLL.XGF_Blocking
        )
        if not ok:
            raise Exception(f'{name}: Failed to capture frame.')

        return frame_buffer, size, dims

    def close(self):
        '''
        Stops capturing, closes capture thread, closes connection.
        '''
        # Existing implementation
        pass


    @property
    def enabled(self):
        '''
        Is capture thread enabled.
        @return: True/False
        '''
        with self.enabled_lock:
            val = self._enabled
        return val


    @enabled.setter
    def enabled(self, value):
        '''
        Signals capture thread to shut down when set to False.
        Otherwise always True.
        '''
        with self.enabled_lock:
            self._enabled = value


    def is_alive(self):
        return self._capture_thread.is_alive()


    def get_property_count(self):
        '''
        Asks the camera how many properties there are.
        '''
        property_count = xdll.XDLL.get_property_count(self.handle)
        return property_count


    def get_property_name(self, idx):
        '''
        Asks the camera for the name of a given property from index
        '''
        return xdll.get_property_name(self.handle, idx).decode('utf-8')


    def get_property_info(self, idx = None, name = None):
        '''
        Asks the camera for the valid range and units of a given property
        '''
        if not name:
            name = self.get_property_name(idx)
        name = name.encode('utf-8')

        info = xdll.get_property_info(self.handle, name)

        return tuple(i.decode('utf-8') for i in info)


    def set_property(self, value, idx = None, name = None, propType = "num"):
        '''
        Sets numerical property
        '''
        if not name:
            name = self.get_property_name(idx)
        name = name.encode('utf-8')

        if propType == "num":
            xdll.set_num_property(self.handle, name, value)
        elif propType == "bool":
            xdll.set_num_property(self.handle, name, value, boolean = True)
        else:
            xdll.set_char_property(self.handle, name, value)

        # Dump frame buffer
        self.capture_single_frame()


    def get_frame_parameters(self):
        return {
            "size" : self.get_frame_size(),
            "dims" : self.get_frame_dims(),
            "pixel": self.get_pixel_size(),
            "dtype": self.get_pixel_dtype()
        }


    def get_frame_size(self):
        '''
        Asks the camera what is the frame size in bytes.
        @return: c_ulong
        '''
        frame_size = xdll.XDLL.get_frame_size(self.handle)  # Size in bytes
        return frame_size


    def get_frame_dims(self):
        '''
        Returns frame dimensions in tuple(height, width).
        @return: tuple (c_ulong, c_ulong)
        '''
        frame_width = xdll.XDLL.get_frame_width(self.handle)
        frame_height = xdll.XDLL.get_frame_height(self.handle)
        # print('width:', frame_width, 'height:', frame_height)
        return frame_height, frame_width


    def get_frame_type(self):
        '''
        Returns enumeration of camera's frame type.
        @return: c_ulong
        '''
        return xdll.XDLL.get_frame_type(self.handle)


    def get_pixel_dtype(self):
        '''
        Returns numpy dtype of the camera's configured data type for frame
        @return: Numpy dtype (np.uint8, np.uint16 or np.uint32)
        '''
        bytes_in_pixel = self.get_pixel_size()
        conversions = (None, np.uint8, np.uint16, None, np.uint32)
        try:
            pixel_dtype = conversions[bytes_in_pixel]
        except:
            raise Exception('Unsupported pixel size %s' % str(bytes_in_pixel))
        if conversions is None:
            raise Exception('Unsupported pixel size %s' % str(bytes_in_pixel))
        return pixel_dtype


    def get_pixel_size(self):
        '''
        Returns a frame pixel's size in bytes.
        @return: int
        '''
        frame_t = xdll.XDLL.get_frame_type(self.handle)
        return xdll.XDLL.pixel_sizes[frame_t]


    def get_frame(self, buffer, frame_t, size, flag=0):
        '''
        Reads a frame from camera. Raises an exception on errors.

        @param buffer: bytes buffer (output) to which a frame is read from
                       the camera.
        @param frame_t: frame type enumeration. Use get_frame_type() to find
                        the native type.
        @param size: frame size in bytes. Use get_frame_dims()
        @param flag: Type of execution. 0 is non-blocking, xdll.XGF_Blocking
                     is blocking.
        @return: True if got frame, otherwise False
        '''
        # frame_buffer = \
        #     np.zeros((frame_size / pixel_size,),
        #              dtype=np.int16)
        # frame_buffer = bytes(frame_size)
        error = xdll.XDLL.get_frame(self.handle,
                                    frame_t,
                                    flag,
                                    # frame_buffer.ctypes.data,
                                    buffer,
                                    size)
        # ctypes.cast(buffer, ctypes.POINTER(ctypes.c))
        if error not in (xdll.XDLL.I_OK, xdll.XDLL.E_NO_FRAME):
            raise Exception(
                'Error while getting frame: %s' % xdll.error2str(error))
        # frame_buffer = np.reshape(frame_buffer, frame_dims)
        return error == xdll.XDLL.I_OK  # , frame_buffer


    def set_handler(self, handler, incl_ctrl_frames=False):
        '''
        Adds a new output to which frames are written.

        @param handler: a file-like object, a stream or object with write()
                        and read() methods.
        '''
        self.handlers.append((handler, incl_ctrl_frames))


    def clear_handlers(self):
        name = 'clear_handlers'
        if not self.is_alive():
            self.handlers.clear()
            print(name, 'Cleared handlers')
        else:
            raise Exception('Can\'t clear handlers when thread is alive')


    def check_thread_exceptions(self):
        name = 'check_thread_exceptions'
        try:
            exc = self.exc_queue.get(block=False)
        except queue.Empty:
            pass  # No exceptions
        else:
            exc_type, exc_obj, exc_trace = exc
            print(name, '%s: %s' % (str(exc_type), str(exc_trace)))
            raise exc

    @kbinterrupt_decorate
    def start_recording(self):
        '''
        Starts recording frames to handlers.
        '''
        self.enabled = True
        self._capture_thread = threading.Thread(name='capture_thread',
                                                target=self.capture_frame_stream)
        self._capture_thread.start()

    @kbinterrupt_decorate
    def wait_recording(self, seconds):
        '''
        Blocks execution and checks there are no exceptions.
        @param seconds: Time how long the function blocks the execution.
        '''
        # self.record_time
        start = time.time()
        while True:
            self.check_thread_exceptions()  # Raises exception
            end = time.time()
            t = end-start
            if end-start >= seconds:
                break
        self._record_time += t
        # time.sleep(seconds)

    @kbinterrupt_decorate
    def stop_recording(self):
        '''
        Stops capturing frames after the latest one is done capturing.
        @return: Metadata tuple array
        '''
        start = time.time()
        self.enabled = False
        self._capture_thread.join(5)
        if self._capture_thread.is_alive():
            raise Exception('Thread didn\'t stop.')
        end = time.time()
        self._record_time += end-start
        error = xdll.XDLL.stop_capture(self.handle)
        if error != xdll.XDLL.I_OK:
            xdll.print_error(error)
            raise Exception(
                'Could not stop capturing. %s' % xdll.error2str(error))
        self.check_thread_exceptions()  # Raises exception

        # Return ENVI metadata about the recording
        frame_dims = self.get_frame_dims()
        frame_type = self.get_frame_type()
        meta = (('samples', frame_dims[1]),
                ('bands', self.frames_count),
                ('lines', frame_dims[0]),
                ('data type',
                 utils.datatype2envitype(
                     'u' + str(xdll.XDLL.pixel_sizes[frame_type]))),
                ('interleave', 'bil'),
                ('byte order', 1),
                ('description', 'Capture time = %d\nFrame time stamps = %s' % (self._record_time, str(self._times))))
        return meta


    def capture_frame_stream(self):
        '''
        Thread function for continuous camera capturing.
        Keeps running until 'enabled' property is set to False.
        '''
        name = 'capture_frame_stream'
        try:
            error = xdll.XDLL.start_capture(self.handle)
            if error != xdll.XDLL.I_OK:
                xdll.print_error(error)
                raise Exception(
                    '%s Starting capture failed! %s' % (name, xdll.error2str(error)))
            if xdll.XDLL.is_capturing(self.handle) == 0:
                for i in range(5):
                    if xdll.XDLL.is_capturing(self.handle) == 0:
                        print(name, 'Camera is not capturing. Retry number %d' % i)
                        time.sleep(0.1)
                    else:
                        break
            if xdll.XDLL.is_capturing(self.handle) == 0:
                raise Exception('Camera is not capturing.')
            elif xdll.XDLL.is_capturing(self.handle):
                self.frames_count = 0
                size = self.get_frame_size()
                dims = self.get_frame_dims()
                frame_t = self.get_frame_type()
                # pixel_size = self.get_pixel_size()
                print(name, 'Size:', size, 'Dims:', dims, 'Frame type:', frame_t)
                frame_buffer = bytes(size)
                # ctrl_frame_buffer = bytearray(4)  # 32 bits
                start_time = utils.get_time()
                while self._enabled:
                    # frame_buffer = \
                    #     np.zeros((size / pixel_size,),
                    #              dtype=np.int16)
                    # buffer = memoryview(frame_buffer)
                    while True:
                        ok = self.get_frame(frame_buffer,
                                            frame_t=frame_t,
                                            size=size,
                                            flag=0)  # Non-blocking
                        # xdll.XGF_Blocking
                        if ok:
                            curr_time = utils.get_time() - start_time
                            self._times.append(curr_time)
                            ctrl_frame_buffer = struct.pack('I', curr_time)  # 4 bytes
                            for h, incl_ctrl_frame in self.handlers:
                                # print(name,
                                #       'Writing to %s' % str(h.__class__.__name__))
                                if incl_ctrl_frame:
                                    h.write(ctrl_frame_buffer)
                                wrote_bytes = h.write(frame_buffer)
                                # print(name,
                                #       'Wrote to %s:' % str(h.__class__.__name__),
                                #       wrote_bytes,
                                #       'bytes')
                            break
                        # else:
                        #     print(name, 'Missed frame', i)
                    self.frames_count += 1
            else:
                raise Exception('Camera is not capturing.')
        except Exception as e:
            self.exc_queue.put(sys.exc_info())
            print(name, '%s(%s): %s' % (type(e).__name__, str(e.errno), e.strerror))
        print(name, 'Thread closed')


    def capture_single_frame(self, dump_buffer = False):
        '''
        Captures a single frame
        '''
        name = 'capture_single_frame'
        frame = None
        error = xdll.XDLL.start_capture(self.handle)

        if error != xdll.XDLL.I_OK:
            xdll.print_error(error)
            raise Exception(
                '%s Starting capture failed! %s' % (name, xdll.error2str(error)))

        if xdll.XDLL.is_capturing(self.handle) == 0:
            for i in range(5):
                if xdll.XDLL.is_capturing(self.handle) == 0:
                    print(name, 'Camera is not capturing. Retry number %d' % i)
                    time.sleep(0.1)
                else:
                    break

        if xdll.XDLL.is_capturing(self.handle) == 0:
            raise Exception('Camera is not capturing.')

        elif xdll.XDLL.is_capturing(self.handle):
            size = self.get_frame_size()
            dims = self.get_frame_dims()
            frame_t = self.get_frame_type()
            frame_buffer = bytes(size)

            if dump_buffer:
                ok = self.get_frame(
                    frame_buffer,
                    frame_t = frame_t,
                    size = size,
                    flag = xdll.XDLL.XGF_Blocking
                )
                frame_buffer = bytes(size)

            ok = self.get_frame(
                frame_buffer,
                frame_t = frame_t,
                size = size,
                flag = xdll.XDLL.XGF_Blocking
            )

        else:
            raise Exception('Camera is not capturing.')

        return frame_buffer, size, dims, frame_t


"""
class XevaImage(object):


    def __init__(self, byte_stream, dims, dtype):
        import io
        if not isinstance(byte_stream, io.BytesIO):
            raise Exception('')
        self.stream = byte_stream

    @contextmanager
    def open(self, mode='r'):
        try:
            yield self
        finally:
            pass


    def read_numpy_array(self, target_order=None):
        ''' Reads BytesIO stream Numpy 3D ndarray '''
        self.stream.read()
        # TODO:
        # map(lambda x: x, self.lines)
        # trans = self._get_permutation_tuple(interleave_order, target_order)
        # data = np.transpose(data, trans)
        # return data
        return 0
"""
