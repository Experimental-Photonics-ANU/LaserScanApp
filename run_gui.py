from laserscan.lasercontrol import LaserSource
from laserscan.gui import LaserScanApp
from laserscan.xevacam.camera import XevaCam
import os
from datetime import datetime


""" Launch the GUI - requires some customization to point to the correct Xeneth control software path """

if __name__ == "__main__":
    try:
        #Create a folder to hold the images and output the folder path.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(script_dir, f"captures_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        print(f"Images will be saved to: {output_dir}")

        #initialize laser
        laser = LaserSource(adapter="GPIB0::1::INSTR", includeSCPI=False)
        print(f"current wavelength: {laser.wavelength}")
        laser.power = True
        laser.write(":OUTP:TRAC OFF")
        cam = XevaCam()
        # cam = XevaCam(calibration=r"C:\Program Files\Xeneth\Calibrations\XS5047_1ms_HG_RT_5047.xca")
        
        #initialize camera
        # cam = camera.XevaCam(calibration='none')
        cam.start_capture(camera_path=r"cam://0", sw_correction=False)
      

        # initialize GUI
        app = LaserScanApp(laser, cam, output_dir)
        app.run()

    finally:
        cam.close()
        print("Camera closed.")
