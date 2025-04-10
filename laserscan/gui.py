from PIL import Image, ImageTk
import customtkinter
import time
import os
from laserscan.aux_funcs import *
from datetime import datetime

default = {
    'power_level': 0,
    'start_wavelength' : 1530,
    'stop_wavelength' : 1560,
    'dwell_time' : 2000,
    'step_size' : 1,
    'integration_time' : 5000,
    'lowgain' : 1
}


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
        self.laser_pow.insert(0, str(default['power_level']))
        self.laser_pow.pack(pady=12, padx=100)

        self.entr_start_w = customtkinter.CTkEntry(master=left_frame, placeholder_text="1530")
        self.entr_start_w.insert(0, str(default['start_wavelength']))
        self.entr_start_w.pack(pady=12, padx=10)

        self.entr_end_w = customtkinter.CTkEntry(master=left_frame, placeholder_text="1560")
        self.entr_end_w.insert(0, str(default['stop_wavelength']))
        self.entr_end_w.pack(pady=12, padx=10)

        self.entr_scan_step = customtkinter.CTkEntry(master=left_frame, placeholder_text="1")
        self.entr_scan_step.insert(0, str(default['step_size']))
        self.entr_scan_step.pack(pady=12, padx=10)

        self.int_time_entry = customtkinter.CTkEntry(master=left_frame, placeholder_text="Integration time (\u00b5s)")
        self.int_time_entry.insert(0, str(default['integration_time']))
        self.int_time_entry.pack(pady=12, padx=10)

        self.lowgain_entry = customtkinter.CTkEntry(master=left_frame, placeholder_text="LowGain (0 or 1)")
        self.lowgain_entry.insert(0, str(default['lowgain']))
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
    print('test gui:')