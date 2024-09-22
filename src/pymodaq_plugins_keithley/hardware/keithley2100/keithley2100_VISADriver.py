import numpy as np
import pyvisa as visa
from pymodaq_plugins_keithley import config
from pymodaq.utils.logger import set_logger, get_module_name
logger = set_logger(get_module_name(__file__))


class Keithley2100VISADriver:
    """VISA class driver for the Keithley 2100 Multimeter/Switch System

    This class relies on pyvisa module to communicate with the instrument via VISA protocol.
    Please refer to the instrument reference manual available at:
    https://PLACEHOLDER.pdf
    https://PLACEHOLDER.pdf
    """
    # List the Keithley instruments the user has configured from the .toml configuration file
    list_instruments = {}
    for instr in config["Keithley", "2100"].keys():
        if "INSTRUMENT" in instr:
            list_instruments[instr] = config["Keithley", "2100", instr, "rsrc_name"]
    logger.info("Configured instruments: {}".format(list(list_instruments.items())))

    # # Non-amps modules
    # non_amp_module = {"MODULE01": False, "MODULE02": False}
    # non_amp_modules_list = ['7701', '7703', '7706', '7707', '7708', '7709']
    #
    # # Channels & modes attributes
    # channels_scan_list = ''
    # modes_channels_dict = {'VOLT:DC': [],
    #                        'VOLT:AC': [],
    #                        'CURR:DC': [],
    #                        'CURR:AC': [],
    #                        'RES': [],
    #                        'FRES': [],
    #                        'FREQ': [],
    #                        'TEMP': []}
    # sample_count_1 = False
    # reading_scan_list = False
    # current_mode = ''

    def __init__(self, rsrc_name):
        """Initialize KeithleyVISADriver class

        :param rsrc_name: VISA Resource name
        :type rsrc_name: string
        """
        self._instr = None
        self.rsrc_name = rsrc_name
        self.instr = ""
        self.configured_modules = {}

    def init_hardware(self, pyvisa_backend='@ivi'):
        """Initialize the selected VISA resource
        
        :param pyvisa_backend: Expects a pyvisa backend identifier or a path to the visa backend dll (ref. to pyvisa)
        :type pyvisa_backend: string
        """
        # Open connexion with instrument
        rm = visa.highlevel.ResourceManager(pyvisa_backend)
        logger.info("Resources detected by pyvisa: {}".format(rm.list_resources(query='?*')))
        try:
            self._instr = rm.open_resource(self.rsrc_name,
                                           write_termination="\n",
                                           read_termination="\n",
                                           )
            self._instr.timeout = 10000
            # Check if the selected resource match the loaded configuration
            model = self.get_idn()[32:36]
            if "21" not in model:
                logger.warning("Driver designed to use Keithley 2100, not {} model. Problems may occur.".format(model))
            for instr in config["Keithley", "2100"]:
                if type(config["Keithley", "2100", instr]) == dict:
                    if self.rsrc_name in config["Keithley", "2100", instr, "rsrc_name"]:
                        self.instr = instr
            logger.info("Instrument selected: {} ".format(config["Keithley", "2100", self.instr, "rsrc_name"]))
            logger.info("Keithley model : {}".format(config["Keithley", "2100", self.instr, "model_name"]))
        except visa.errors.VisaIOError as err:
            logger.error(err)

    def clear_buffer(self):
        # Default: auto clear when scan start
        self._instr.write("TRAC:CLE")

    def clear_buffer_off(self):
        # Disable buffer auto clear
        self._instr.write("TRAC:CLE:AUTO OFF")

    def clear_buffer_on(self):
        # Disable buffer auto clear
        self._instr.write("TRAC:CLE:AUTO ON")

    def close(self):
        self._instr.write("ROUT:OPEN:ALL")
        self._instr.close()

    def data(self):
        """Get data from instrument

        Make the Keithley perform 3 actions: init, trigger, fetch. Then process the answer to return 3 variables:
        - The answer (string)
        - The measurement values (numpy array)
        - The timestamp of each measurement (numpy array)
        """
        if not self.sample_count_1:
            # Initiate scan
            self._instr.write("INIT")
            # Trigger scan
            self._instr.write("*TRG")
            # Get data (equivalent to TRAC:DATA? from buffer)
            str_answer = self._instr.query("FETCH?")
        else:
            str_answer = self._instr.query("FETCH?")
        # Split the instrument answer (MEASUREMENT,TIME,READING COUNT) to create a list
        list_split_answer = str_answer.split(",")

        # MEASUREMENT & TIME EXTRACTION
        list_measurements = list_split_answer[::3]
        str_measurements = ''
        list_times = list_split_answer[1::3]
        str_times = ''
        for j in range(len(list_measurements)):
            if not j == 0:
                str_measurements += ','
                str_times += ','
            for l1 in range(len(list_measurements[j])):
                test_carac = list_measurements[j][-(l1+1)]
                # Remove non-digit characters (units)
                if test_carac.isdigit():
                    if l1 == 0:
                        str_measurements += list_measurements[j]
                    else:
                        str_measurements += list_measurements[j][:-l1]
                    break
            for l2 in range(len(list_times[j])):
                test_carac = list_times[j][-(l2+1)]
                # Remove non-digit characters (units)
                if test_carac.isdigit():
                    if l2 == 0:
                        str_times += list_times[j]
                    else:
                        str_times += list_times[j][:-l2]
                    break

        # Split created string to access each value
        list_measurements_values = str_measurements.split(",")
        list_times_values = str_times.split(",")
        # Create numpy.array containing desired values (float type)
        array_measurements_values = np.array(list_measurements_values, dtype=float)
        if not self.sample_count_1:
            array_times_values = np.array(list_times_values, dtype=float)
        else:
            array_times_values = np.array([0], dtype=float)

        return str_answer, array_measurements_values, array_times_values

    def get_card(self):
        # Query switching module
        return self._instr.query("*OPT?")
    
    def get_error(self):
        # Ask the keithley to return the last current error
        return self._instr.query("SYST:ERR?")
    
    def get_idn(self):
        # Query identification
        return self._instr.query("*IDN?")
    
    def init_cont_off(self):
        # Disable continuous initiation
        self._instr.write("INIT:CONT OFF")
        
    def init_cont_on(self):
        # Enable continuous initiation
        self._instr.write("INIT:CONT ON")

    def mode_temp_frtd(self, channel, transducer, frtd_type,):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:FRTD:TYPE " + frtd_type + "," + channel)

    def mode_temp_tc(self, channel, transducer, tc_type, ref_junc,):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:TC:TYPE " + tc_type + "," + channel)
        self._instr.write("TEMP:RJUN:RSEL " + ref_junc + "," + channel)

    def mode_temp_ther(self, channel, transducer, ther_type,):
        self._instr.write("TEMP:TRAN " + transducer + "," + channel)
        self._instr.write("TEMP:THER:TYPE " + ther_type + "," + channel)
    
    def reset(self):
        # Clear measurement event register
        self._instr.write("*CLS")
        # One-shot measurement mode (Equivalent to INIT:COUNT OFF)
        self._instr.write("*RST")

    def read(self):
        return float(self._instr.query("READ?"))

    def set_mode(self, mode):
        """Define whether the Keithley will scan all the scan_list or only channels in the selected mode

        :param mode: Supported modes: 'SCAN_LIST', 'VDC', 'VAC', 'IDC', 'IAC', 'R2W', 'R4W', 'FREQ' and 'TEMP'
        :type mode: string
        """
        mode = mode.upper()
        
        # FRONT panel
        if "SCAN" not in mode:
            self.init_cont_on()
            self.sample_count_1 = True
            self.reading_scan_list = False
            self._instr.write("FUNC '" + mode + "'")

        # REAR panel
        else:
            self.clear_buffer()
            # Init continuous disabled
            self.init_cont_off()
            mode = mode[5:]
            self.current_mode = mode
            if 'SCAN_LIST' in mode:
                self.reading_scan_list = True
                self.sample_count_1 = False
                channels = '(@' + self.channels_scan_list + ')'
                # Set to perform 1 to INF scan(s)
                self._instr.write("TRIG:COUN 1")
                # Trigger immediately after previous scan end if IMM
                self._instr.write("TRIG:SOUR BUS")
                # Set to scan <n> channels
                samp_count = 1 + channels.count(',')
                self._instr.write("SAMP:COUN "+str(samp_count))
                # Disable scan if currently enabled
                self._instr.write("ROUT:SCAN:LSEL NONE")
                # Set scan list channels
                self._instr.write("ROUT:SCAN " + channels)
                # Start scan immediately when enabled and triggered
                self._instr.write("ROUT:SCAN:TSO IMM")
                # Enable scan
                self._instr.write("ROUT:SCAN:LSEL INT")

            else:
                self.reading_scan_list = False
                # Select channels in the channels list (config file) matching the requested mode
                channels = '(@' + str(self.modes_channels_dict[mode])[1:-1] + ')'
                # Set to perform 1 to INF scan(s)
                self._instr.write("TRIG:COUN 1")
                # Set to scan <n> channels
                samp_count = 1+channels.count(',')
                self._instr.write("SAMP:COUN "+str(samp_count))
                if samp_count == 1:
                    self.init_cont_on()
                    # Trigger definition
                    self._instr.write("TRIG:SOUR IMM")
                    # Disable scan if currently enabled
                    self._instr.write("ROUT:SCAN:LSEL NONE")
                    self._instr.write("ROUT:CLOS " + channels)
                    
                    self._instr.write("FUNC '" + mode + "'")
                    logger.info("rear sample count: {}".format(self.sample_count_1))
                    if not self.sample_count_1:
                        self.sample_count_1 = True
                    self.reading_scan_list = False
                else:
                    self.sample_count_1 = False
                    # Trigger definition
                    self._instr.write("TRIG:SOUR BUS")
                    # Disable scan if currently enabled
                    self._instr.write("ROUT:SCAN:LSEL NONE")
                    # Set scan list channels
                    self._instr.write("ROUT:SCAN " + channels)
                    # Start scan immediately when enabled and triggered
                    self._instr.write("ROUT:SCAN:TSO IMM")
                    # Enable scan
                    self._instr.write("ROUT:SCAN:LSEL INT")
                
            return channels
        
    def stop_acquisition(self):
        # If scan in process, stop it
        self._instr.write("ROUT:SCAN:LSEL NONE")

    def user_command(self):
        command = input('Enter here a command you want to send directly to the Keithley [if None, press enter]: ')
        if command != '':
            if command[-1] == "?":
                print(self._instr.query(command))
            else:
                self._instr.write(command)
            self.user_command()
        else:
            pass


if __name__ == "__main__":
    try:
        print("In main")

        # You can use this main section for:
        # - Testing connexion and communication with your instrument
        # - Testing new methods in developer mode

        RM = visa.ResourceManager("@ivi")
        print("list resources", RM.list_resources())

        # K2100 Instance of KeithleyVISADriver class (replace ASRL1::INSTR by the name of your resource)
        k2100 = Keithley2100VISADriver("ASRL1::INSTR")
        k2100.init_hardware()
        print("IDN?")
        print(k2100.get_idn())
        k2100.reset()

        # Daq_viewer simulation first run
        k2100.set_mode(str(input('Enter which mode you want to scan \
        [scan_scan_list, scan_volt:dc, scan_r2w, scan_temp...]:')))
        print('Manual scan example of command set to send directly: >init >*trg >trac:data?')
        k2100.user_command()
        print('Automatic scan example with 2 iterations')
        for i in range(2):
            print(k2100.data())
        print(k2100.data())

        # Daq_viewer simulation change mode
        k2100.set_mode(str(input('Enter which mode you want to scan \
        [scan_scan_list, scan_volt:dc, scan_r2w, scan_temp...]:')))
        for i in range(2):
            print(k2100.data())
        print(k2100.data())

        k2100.clear_buffer()
        k2100.close()

        print("Out")

    except Exception as e:
        print("Exception ({}): {}".format(type(e), str(e)))
