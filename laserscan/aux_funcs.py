import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
import time

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