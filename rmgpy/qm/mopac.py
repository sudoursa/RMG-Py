import os

import openbabel
import cclib.parser
import logging
from subprocess import Popen, PIPE

from qmdata import CCLibData
from molecule import QMMolecule, TDPropertiesCalculator

class Mopac:
    
    directory = 'QMfiles'
    inputFileExtension = '.mop'
    outputFileExtension = '.out'
    executablePath = os.path.join(os.getenv('MOPAC_DIR', default="/opt/mopac") , 'MOPAC2009.exe')
    
    usePolar = False#use polar keyword in MOPAC
    
    "Keywords for the multiplicity"
    multiplicityKeywords = {}
    multiplicityKeywords[1] = ''
    multiplicityKeywords[2] = 'uhf doublet'
    multiplicityKeywords[3] = 'uhf triplet'
    multiplicityKeywords[4] = 'uhf quartet'
    multiplicityKeywords[5] = 'uhf quintet'
    multiplicityKeywords[6] = 'uhf sextet'
    multiplicityKeywords[7] = 'uhf septet'
    multiplicityKeywords[8] = 'uhf octet'
    multiplicityKeywords[9] = 'uhf nonet'
    
    #: List of phrases that indicate failure
    #: NONE of these must be present in a succesful job.
    failureKeys = [
                   'IMAGINARY FREQUENCIES',
                   'EXCESS NUMBER OF OPTIMIZATION CYCLES',
                   'NOT ENOUGH TIME FOR ANOTHER CYCLE',
                   ]
    #: List of phrases to indicate success.
    #: ALL of these must be present in a successful job.
    successKeys = [
                   'DESCRIPTION OF VIBRATIONS',
                  ]

    @property
    def outputFilePath(self):
        """Get the Mopac output file name."""
        return os.path.join(self.directory, self.geometry.uniqueID + self.outputFileExtension)

    @property
    def inputFilePath(self):
        """Get the Mopac input file name."""
        return os.path.join(self.directory, self.geometry.uniqueID + self.inputFileExtension)

    def writeInputFile(self, attempt, top_keys, bottom_keys, polar_keys):
        """
        Using the :class:`Geometry` object, write the input file
        for the `attmept`th attempt.
        """
        
        obConversion = openbabel.OBConversion()
        obConversion.SetInAndOutFormats("mol", "mop")
        mol = openbabel.OBMol()
        
        if attempt <= self.scriptAttempts: #use UFF-refined coordinates
            obConversion.ReadFile(mol, self.geometry.getRefinedMolFilePath() )
        else:
            obConversion.ReadFile(mol, self.geometry.getCrudeMolFilePath() )
        
        mol.SetTitle(self.geometry.uniqueIDlong)
        obConversion.SetOptions('k', openbabel.OBConversion.OUTOPTIONS)
        
        input_string = obConversion.WriteString(mol)
        
        with open(self.inputFilePath, 'w') as mopacFile:
            mopacFile.write(top_keys)
            mopacFile.write(input_string)
            mopacFile.write('\n')
            mopacFile.write(bottom_keys)
            if self.usePolar:
                mopacFile.write('\n\n\n')
                mopacFile.write(polar_keys)


    def run(self):
        # submits the input file to mopac
        process = Popen([self.executablePath, self.inputFilePath])
        process.communicate()# necessary to wait for executable termination!
    
        return self.verifyOutputFile()
        
    def verifyOutputFile(self):
        """
        Check's that an output file exists and was successful.
        
        Returns a boolean flag that states whether a successful MOPAC simulation already exists for the molecule with the 
        given (augmented) InChI Key.
        
        The definition of finding a successful simulation is based on these criteria:
        1) finding an output file with the file name equal to the InChI Key
        2) NOT finding any of the keywords that are denote a calculation failure
        3) finding all the keywords that denote a calculation success.
        4) finding a match between the InChI of the given molecule and the InchI found in the calculation files
        
        If any of the above criteria is not matched, False will be returned and the procedures to start a new calculation 
        will be initiated.
        """
        
        if not os.path.exists(self.outputFilePath):
            logging.info("Output file {0} does not exist.".format(self.outputFilePath))
            return False
    
        InChIMatch=False #flag (1 or 0) indicating whether the InChI in the file matches InChIaug this can only be 1 if InChIFound is also 1
        InChIFound=False #flag (1 or 0) indicating whether an InChI was found in the log file
        
        # Initialize dictionary with "False"s 
        successKeysFound = dict([(key, False) for key in self.successKeys])
        
        with open(self.outputFilePath) as outputFile:
            for line in outputFile:
                line = line.strip()
                
                for element in self.failureKeys: #search for failure keywords
                    if element in line:
                        logging.error("MOPAC output file contains the following error: %s")%element
                        return False
                    
                for element in self.successKeys: #search for success keywords
                    if element in line:
                        successKeysFound[element] = True
               
                if "InChI=" in line:
                    logFileInChI = line #output files should take up to 240 characters of the name in the input file
                    InChIFound = True
                    if logFileInChI == self.geometry.uniqueIDlong:
                        InChIMatch = True
                    else:
                        logging.info("InChI in log file didn't match that in geometry.")
        
        # Check that ALL 'success' keywords were found in the file.
        if not all( successKeysFound.values() ):
            logging.error('Not all of the required keywords for sucess were found in the output file!')
            return False
        
        if not InChIFound:
            logging.error("No InChI was found in the MOPAC output file {0}".format(self.outputFilePath))
            return False
        
        if InChIMatch:
            logging.info("Successful MOPAC quantum result found in {0}".format(self.outputFilePath))
            # " + self.molfile.name + " ("+self.molfile.InChIAug+") has been found. This log file will be used.")
            return True
        
        #InChIs do not match (most likely due to limited name length mirrored in log file (240 characters), but possibly due to a collision)
        return self.checkForInChiKeyCollision(logFileInChI) # Not yet implemented!

    def read():
        # reads the output file
        import ipdb; ipdb.set_trace()
        pass
    
    def calculate():
        # calculators for the parsing
        import ipdb; ipdb.set_trace()
        pass
        
    def parse(self):
        """
        Parses the results of the Mopac calculation, and returns a CCLibData object.
        """
        parser = cclib.parser.Mopac(self.outputFilePath)
        parser.logger.setLevel(logging.ERROR) #cf. http://cclib.sourceforge.net/wiki/index.php/Using_cclib#Additional_information
        
        cclibData = parser.parse()
        radicalNumber = sum([i.radicalElectrons for i in self.molecule.atoms])
        
        qmData = CCLibData(cclibData, radicalNumber+1)
            
        return qmData

class MopacMol(QMMolecule, Mopac):

    def generateQMData(self):
        """
        Calculate the QM data and return a QMData object.
        """

        self.createGeometry()

        success = False
        method = MopacMolPM3(self)

        if self.verifyOutputFile():
            logging.info("Found a successful output file already; using that.")
        else:
            for attempt in range(1, self.maxAttempts+1):
                top_keys, bottom_keys, polar_keys = method.inputFileKeys( (attempt-1)%self.scriptAttempts+1 )
                self.writeInputFile(attempt, top_keys, bottom_keys, polar_keys)
                success = self.run()
                if success:
                    logging.info('Attempt {0} of {1} on species {2} succeeded.'.format(attempt, self.maxAttempts, self.molecule.toAugmentedInChI()))
                    break
            else:
                raise Exception('QM thermo calculation failed for {0}.'.format(self.molecule.toAugmentedInChI()))
        result = self.parse() # parsed in cclib
        return result


class MopacMolPM3(MopacMol):

    "Keywords that will be added at the top and bottom of the qm input file"
    keywords = [
                ("precise nosym", "oldgeo thermo nosym precise "),
                ("precise nosym gnorm=0.0 nonr", "oldgeo thermo nosym precise "),
                ("precise nosym gnorm=0.0", "oldgeo thermo nosym precise "),
                ("precise nosym gnorm=0.0 bfgs", "oldgeo thermo nosym precise "),
                ("precise nosym recalc=10 dmax=0.10 nonr cycles=2000 t=2000", "oldgeo thermo nosym precise "),
                ]

    scriptAttempts = len(keywords)
    maxAttempts = 2 * scriptAttempts

    def inputFileKeys(self, attempt):
        """
        Inherits the writeInputFile methods from mopac.py
        """
        multiplicity_keys = self.multiplicityKeywords[self.molecule.geometry.multiplicity]

        top_keys = "pm3 {0} {1}".format(
                multiplicity_keys,
                self.keywordsTop[attempt],
                )
        bottom_keys = "{0} pm3 {1}".format(
                self.keywordsBottom[attempt],
                multiplicity_keys,
                )
        polar_keys = "oldgeo {0} nosym precise pm3 {1}".format(
                'polar' if self.molecule.geometry.multiplicity == 1 else 'static',
                multiplicity_keys,
                )

        return top_keys, bottom_keys, polar_keys