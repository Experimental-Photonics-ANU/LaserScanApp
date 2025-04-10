# -*- coding: utf-8 -*-
'''add integration adjustment'''
from PIL import Image, ImageTk
import customtkinter
import numpy as np
import time
import xevacam.camera as camera
import pandas as pd
import os
import matplotlib.pyplot as plt
from pymeasure.instruments import Instrument
import laserscan.default_gui_params as default_gui_params
from datetime import datetime


class LaserSource(Instrument):
    '''
    Encapsulates the class used to control the laser. Provides control over parameters
    such as power, wavelength range, scanning step size, etc.
    '''
    def __init__(self, adapter, name="Laser Source", **kwargs):
        super().__init__(adapter, name, **kwargs)

    @property
    def power(self):
        '''Laser switch status reading'''
        return self.ask(":OUTPut?").strip() == "1"

    @power.setter
    def power(self, state):
        '''Laser switch control'''
        self.write(f":OUTPut {1 if state else 0}")

    power_level = Instrument.control(
        ":SOUR:POW:LEV?", "SOUR:POW:LEV %0.3f", "set and query the power in dBm"
    )

    start_wavelength = Instrument.control(
        "WAVE:STAR?", "WAVE:STAR %0.3f", "set and query the starting wavelength"
    )

    stop_wavelength = Instrument.control(
        "WAVE:STOP?", "WAVE:STOP %0.3f", "set and query the stop wavelength"
    )

    @property
    def wavelength(self):
        '''Current wavelength reading'''
        return float(self.ask(":WAVelength?").strip())

    @wavelength.setter
    def wavelength(self, value):
        '''Current wavelength setting'''
        if not (1500 <= value <= 1570):
            raise ValueError("Wavelength must be between 1500 and 1570 nm.")
        self.write(f":WAVelength {value:.2f}")

    dwell_time = Instrument.control(
        "WAVE:DWEL?", "WAVE:DWEL %0.3f", "set and query the dwell time (ms)"
    )

    step_size = Instrument.control(
        "WAVE:STEP?", "WAVE:STEP %0.3f", "set and query the step size (nm)"
    )

def buffer2frame(frame_buffer, **kwargs):
    '''Convert the buffer raw data collected by the camera into a
    two-dimensional image matrix.'''
    return np.frombuffer(
        frame_buffer,
        dtype=kwargs["dtype"],
        count=int(kwargs["size"] / kwargs["pixel"])
    ).reshape(kwargs["dims"]).astype(np.int16)

def capture_and_save_image(c, wavelength_nm, integration_time_us, output_dir):
    '''
    Call the camera to acquire images and save them as CSV files.
    '''
    
    params = c.get_frame_parameters()

    c.set_property(integration_time_us, name="IntegrationTime")
    time.sleep(0.2)
    for _ in range(10):  
        c.capture_frame_only()

    frame, *_ = c.capture_frame_only()
    captured_frame = buffer2frame(frame, **params)

    base_name = f"image_{wavelength_nm:.2f}nm_{integration_time_us}us"
    csv_path = os.path.join(output_dir, f"{base_name}.csv")
    png_path = os.path.join(output_dir, f"{base_name}.png")

    pd.DataFrame(captured_frame).to_csv(csv_path, index=False)
    print(f"Saved CSV: {csv_path}")

    log_data = np.log1p(captured_frame)
    plt.figure(figsize=(7, 5))
    plt.imshow(log_data, cmap='gray')
    plt.title(f"{base_name} (log-scaled)")
    plt.colorbar(label='Log(1 + Pixel Intensity)')
    plt.tight_layout()
    plt.savefig(png_path)
    plt.close()  
    print(f"Saved image: {png_path}")
    return csv_path

class LaserScanApp:
    ''' GUI setup '''
    def __init__(self, laser, cam, output_dir):
        self.laser = laser
        self.cam = cam
        self.csv_files = []
        self.should_quit = False
        self.output_dir = output_dir

        self.current_wl = None
        self.start_wl = None
        self.stop_wl = None
        self.step_size = None

        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("dark-blue")

        self.root = customtkinter.CTk()
        self.root.title("PSFAuto")
        self.root.geometry("1200x800")
        self.build_ui()

    def build_ui(self):
        """Constructs the GUI layout with all necessary input and control elements."""
        main_frame = customtkinter.CTkFrame(master=self.root)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        left_frame = customtkinter.CTkFrame(master=main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        right_frame = customtkinter.CTkFrame(master=main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.SysMSGs = customtkinter.CTkLabel(master=left_frame, text="")
        self.SysMSGs.pack(pady=12, padx=10)

        self.laser_pow = customtkinter.CTkEntry(master=left_frame, placeholder_text="0")
        self.laser_pow.insert(0, str(default_gui_params.power_level))
        self.laser_pow.pack(pady=12, padx=100)

        self.entr_start_w = customtkinter.CTkEntry(master=left_frame, placeholder_text="1530")
        self.entr_start_w.insert(0, str(default_gui_params.start_wavelength))
        self.entr_start_w.pack(pady=12, padx=10)

        self.entr_end_w = customtkinter.CTkEntry(master=left_frame, placeholder_text="1560")
        self.entr_end_w.insert(0, str(default_gui_params.stop_wavelength))
        self.entr_end_w.pack(pady=12, padx=10)

        self.entr_scan_step = customtkinter.CTkEntry(master=left_frame, placeholder_text="1")
        self.entr_scan_step.insert(0, str(default_gui_params.step_size))
        self.entr_scan_step.pack(pady=12, padx=10)

        self.int_time_entry = customtkinter.CTkEntry(master=left_frame, placeholder_text="Integration time (\u00b5s)")
        self.int_time_entry.insert(0, str(default_gui_params.integration_time))
        self.int_time_entry.pack(pady=12, padx=10)

        self.lowgain_entry = customtkinter.CTkEntry(master=left_frame, placeholder_text="LowGain (0 or 1)")
        self.lowgain_entry.insert(0, str(default_gui_params.lowgain))
        self.lowgain_entry.pack(pady=12, padx=10)

        self.disp_w = customtkinter.CTkEntry(master=left_frame, placeholder_text="Display Wavelength")
        self.disp_w.pack(pady=12, padx=10)

        self.set_btn = customtkinter.CTkButton(master=left_frame, text="Set", command=self.SET)
        self.set_btn.pack(pady=12, padx=10)

        self.next_btn = customtkinter.CTkButton(master=left_frame, text="Next", command=self.NEXT)
        self.next_btn.pack(pady=12, padx=10)

        self.quit_btn = customtkinter.CTkButton(master=left_frame, text="Quit", command=self.QUIT)
        self.quit_btn.pack(pady=12, padx=10)

        self.image_label = customtkinter.CTkLabel(master=right_frame, text='')
        self.image_label.pack(pady=12, padx=10)


    def SET(self):
        try:
            self.laser.power_level = float(self.laser_pow.get())
        except ValueError:
            self.SysMSGs.configure(text="Laser power not a number")
            return

        try:
            self.start_wl = float(self.entr_start_w.get())
        except ValueError:
            self.SysMSGs.configure(text="Start wavelength not a number")
            return

        try:
            self.stop_wl = float(self.entr_end_w.get())
        except ValueError:
            self.SysMSGs.configure(text="End wavelength not a number")
            return

        try:
            self.step_size = float(self.entr_scan_step.get())
        except ValueError:
            self.SysMSGs.configure(text="Step size not a number")
            return

        try:
            self.integration_time = float(self.int_time_entry.get())
        except ValueError:
            self.SysMSGs.configure(text="Integration time not a number")
            return

        try:
            lowgain_val = int(self.lowgain_entry.get())
            if lowgain_val not in (0, 1):
                raise ValueError("LowGain must be 0 or 1")
            self.cam.set_property(lowgain_val, name="LowGain", propType="bool")
        except Exception as e:
            self.SysMSGs.configure(text=f"LowGain setting failed: {e}")
            return

        self.current_wl = self.start_wl

        try:
            self.laser.start_wavelength = self.start_wl
            self.laser.stop_wavelength = self.stop_wl
            self.laser.step_size = self.step_size
            self.laser.power = True
            self.laser.write("OUTP:SCAN:STAR -4")
        except Exception as e:
            self.SysMSGs.configure(text=f"Failed to restart scan: {e}")
            return

        self.disp_w.delete(0, 'end')
        self.disp_w.insert(0, f"{self.current_wl:.2f} nm")
        self.SysMSGs.configure(text="New scan parameters loaded")
        
        csv_path = capture_and_save_image(
        self.cam,
        wavelength_nm=self.current_wl,
        integration_time_us=self.integration_time,
        output_dir=self.output_dir
        )
        self.csv_files.append(csv_path)
        
        img_path = csv_path.replace('.csv', '.png')
        img = Image.open(img_path)
        img = img.resize((400, 300))
        tk_img = ImageTk.PhotoImage(img)
        self.image_label.configure(image=tk_img)
        self.image_label.image = tk_img



    def NEXT(self):
        if self.should_quit:
            return

        if self.current_wl is None or self.step_size is None:
            self.SysMSGs.configure(text="Please press SET first.")
            return

        self.laser.write(":OUTP:SCAN:STEP\n")
        time.sleep(0.5)

        self.current_wl += self.step_size

        if self.current_wl > self.stop_wl:
            self.SysMSGs.configure(text="Reached stop wavelength.")
            return

        self.disp_w.delete(0, 'end')
        self.disp_w.insert(0, f"{self.current_wl:.2f} nm")

        csv_path = capture_and_save_image(
            self.cam,
            wavelength_nm=self.current_wl,
            integration_time_us=self.integration_time,
            output_dir=self.output_dir
        )
        self.csv_files.append(csv_path)

        png_path = csv_path.replace('.csv', '.png')
        img = Image.open(png_path)
        img = img.resize((400, 300))
        tk_img = ImageTk.PhotoImage(img)  

        self.image_label.configure(image=tk_img)
        self.image_label.image = tk_img



    def QUIT(self):
        self.should_quit = True
        try:
            self.cam.close()
            self.laser.write(":OUTP:SCAN:ABOR")
        except Exception as e:
            print(f"Error while closing: {e}")
        self.root.destroy()

    def run(self):
        self.root.mainloop()

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

        # cam = camera.XevaCam()
        cam = camera.XevaCam(calibration=r"C:\Program Files\Xeneth\Calibrations\XS5047_1ms_HG_RT_5047.xca")
        
        #initialize camera
        # cam = camera.XevaCam(calibration='none')
        cam.start_capture(camera_path='cam://0', sw_correction=True)
      

        # initialize GUI
        app = LaserScanApp(laser, cam, output_dir)
        app.run()

    finally:
        cam.close()
        print("Camera closed.")
