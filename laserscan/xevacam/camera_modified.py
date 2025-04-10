
import xevacam.xevadll as xdll
import threading
import queue

class XevaCam(object):
    def __init__(self, calibration=''):
        '''
        Constructor
        @param calibration: Bytes string path to the calibration file (.xca)
        '''
        self.handle = 0
        self.calibration = calibration.encode('utf-8')
        self._enabled = False
        self.enabled_lock = threading.Lock()
        self.handlers = []
        self.exc_queue = queue.Queue()
        self._capture_thread = threading.Thread(name='capture_thread',
                                                target=self.capture_frame_stream)
        self._record_time = 0
        self._times = []

    def open(self, camera_path='cam://0', sw_correction=True):
        '''
        Opens connection to the camera.
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
        print('Camera opened successfully.')

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
        pass  # Placeholder for existing code.

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
        try:
            if xdll.XDLL.is_capturing(self.handle):
                print('Stop capturing...')
                error = xdll.XDLL.stop_capture(self.handle)
                if error != xdll.XDLL.I_OK:
                    xdll.print_error(error)
                    raise Exception('Could not stop capturing. Error: ' + xdll.error2str(error))
                print('Capture stopped successfully.')
                self.enabled = False

            if self._capture_thread.is_alive():
                print('Waiting for the capture thread to terminate...')
                self._capture_thread.join(timeout=1)
                if self._capture_thread.is_alive():
                    raise Exception('Capture thread did not terminate properly.')

        except Exception as e:
            print('Error during camera closure:', e)
            raise

        finally:
            if xdll.XDLL.is_initialised(self.handle):
                print('Closing camera connection...')
                xdll.XDLL.close_camera(self.handle)
                print('Camera connection closed.')

            self.handle = 0
            print('Camera handle reset to 0.')
