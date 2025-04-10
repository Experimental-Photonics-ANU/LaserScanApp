from pymeasure.instruments import Instrument

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


if __name__ == "__main__":
    print('test lasercontrol:')