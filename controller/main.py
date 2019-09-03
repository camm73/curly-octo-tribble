import RPi.GPIO as GPIO
import time
import tkinter as tk
import traceback
import threading
import json

class Main():

    def __init__(self):
        self.pumps = [26, 19, 13, 6, 5, 21, 20, 16]
        self.polarityPins = [17, 27] #Pin 17 is #1 and Pin #27 is #2
        self.polarityNormal = True
        self.cocktailNames = {}
        self.cocktailIngredients = {}
        self.cocktailAmounts = {}
        self.cocktailButtons = {}
        self.cocktailNumbers = {}
        self.cocktailAvailable = {}
        self.pumpMap = {}
        self.pumpNumbers = {}
        self.pumpFull = {}
        self.cocktailCount = 0
        self.pumpTime = 18
        self.cleanTime = 6
        self.shotVolume = 44 #mL
        self.busy_flag = False
        self.window = None

        #Mode 0 is GUI, Mode 1 is Buttons
        self.setMode()

        self.setupPins()
        self.loadPumpMap()
        self.loadCocktails()

        #Button Mode
        if(self.mode == 1):
            self.buttonThread = threading.Thread(target=self.setupButtons)
            self.buttonThread.daemon = True
            self.buttonThread.start()
        elif(self.mode == 0):
            print("GUI MODE!")

    #Sets up pins by setting gpio mode and setting initial output
    def setupPins(self):
        try:
            print("Setting up pump pins...")
            GPIO.setmode(GPIO.BCM)
            for pin in self.pumps:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

            #Turn on signal for #1 relay
            GPIO.setup(self.polarityPins[0], GPIO.OUT)
            GPIO.output(self.polarityPins[0], GPIO.LOW)

            # Turn off signal for #2 relay
            GPIO.setup(self.polarityPins[1], GPIO.OUT)
            GPIO.output(self.polarityPins[1], GPIO.HIGH)
            print("Pins successfully setup!")
        except Exception as e:
            print("Error setting up pump pins: " + str(e))
            exit(1)

    #Test function that runs all of the pumps for 3 seconds each
    def testPumps(self):
        try:
            for pin in self.pumps:
                GPIO.output(pin, GPIO.LOW)
                print("Turning on pin " + str(pin))
                time.sleep(3)
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(1)
        except KeyboardInterrupt:
            print('Exitting early')
            GPIO.cleanup()
            exit()

    def loadCocktails(self):
        #Load cocktails from json file
        data = {}
        with open('cocktails.json', 'r') as file:
            data = json.load(file)

        i = 0
        #Loads all cocktail details into separate python objects
        for cocktails in data['cocktails']:
            self.cocktailNames[i] = (str(data['cocktails'][i]['name']))
            self.cocktailIngredients[i] = data['cocktails'][i]['ingredients']
            self.cocktailAmounts[i] = data['cocktails'][i]['amounts']
            self.cocktailNumbers[str(data['cocktails'][i]['name'])] = i
            self.cocktailAvailable[str(data['cocktails'][i]['name'])] = self.isAvailable(str(data['cocktails'][i]['name']))
            print(self.cocktailAvailable[str(data['cocktails'][i]['name'])])
            i = i+1
        self.cocktailCount = i

    #Scans through the ingredients on each pump and the ingredients needed for this cocktail to determine availability
    def isAvailable(self, cocktailName):
        cocktailNumber = self.cocktailNumbers[cocktailName]
        
        for ingredient in self.cocktailIngredients[cocktailNumber]:
            if(ingredient not in self.pumpMap.keys()):
                print(ingredient + " not available!")
                return False
        return True
    
    #Loads pump/ingredient map from json file (ALSO SET PUMP NUMBERS)
    def loadPumpMap(self):
        data = {}
        with open('pumpMap.json', 'r') as file:
            data = json.load(file)

        #print('Here is the data: ' + str(data))
        self.pumpFull = data
        
        mapObject = {}
        for item in data:
            mapObject[item] = data[item]["pump"]
            self.pumpNumbers[data[item]["pump"]] = item
        #Store pumpMap data in pumpMap dict
        self.pumpMap = mapObject

    #Function that crafts the cocktail requested
    def makeCocktail(self, cocktailName):
        if(self.busy_flag):
            #TODO add some feedback message
            print('Busy making cocktail!')
            return False
        num = self.cocktailNumbers[cocktailName]
        
        #Check whether the cocktail is available or not
        if(not self.cocktailAvailable[cocktailName]):
            print('This cocktail is not avialable!')
            return False
        
        #Check whether there are enough ingredients
        if(not self.canMakeCocktail(cocktailName)):
            print('Not enough ingredients to make this cocktail.')
            return False
        
        print('Making cocktail ' + str(self.cocktailNames[num]))
        self.busy_flag = True
        self.setupPins()

        #Now we need to turn on pumps for respective ingredients for specified times
        i = 0
        waitTime = 0
        biggestAmt = 0
        for ingredient in self.cocktailIngredients[num]:
            pumpThread = threading.Thread(target=self.pumpToggle, args=[self.pumpMap[ingredient], self.cocktailAmounts[num][i]])
            pumpThread.start()

            #Adjust volume tracking for each of the pumps
            print('Ingredient: ' + str(ingredient))
            self.adjustVolumeData(ingredient, self.cocktailAmounts[num][i])

            if(self.cocktailAmounts[num][i] > biggestAmt):
                biggestAmt = self.cocktailAmounts[num][i]
            i += 1
        
        waitTime = biggestAmt*self.pumpTime
        print('Wait Time: ' + str(waitTime))
        time.sleep(waitTime + 2)
        print("Done making cocktail!")

        self.busy_flag = False
        return True

    #Toggles specific pumps for specific amount of time
    def pumpToggle(self, num, amt):
        pumpPinIndex = num - 1
        pumpPin = self.pumps[pumpPinIndex]
        GPIO.output(pumpPin, GPIO.LOW)
        time.sleep(self.pumpTime*amt)
        GPIO.output(pumpPin, GPIO.HIGH)

    #Turns on a specific pump for indefinite amount of time
    def pumpOn(self, num):
        pumpPinIndex = num - 1
        pumpPin = self.pumps[pumpPinIndex]
        print('Turning on pump: ' + str(num))
        GPIO.output(pumpPin, GPIO.LOW)

    #Turns off a specific pump for indefinite amount of time
    def pumpOff(self, num):
        pumpPinIndex = num - 1
        pumpPin = self.pumps[pumpPinIndex]
        print("Turning off pump: " + str(num))
        GPIO.output(pumpPin, GPIO.HIGH)

    
    #Reverse the polarity of the motors
    def reversePolarity(self):
        if(self.polarityNormal):
            #Turn off signal for #1 relay
            GPIO.output(self.polarityPins[0], GPIO.HIGH)

            #Turn on signal for #2 relay
            GPIO.output(self.polarityPins[1], GPIO.LOW)
            self.polarityNormal = False
        else:
            #Turn on signal for #1 relay
            GPIO.output(self.polarityPins[0], GPIO.LOW)

            # Turn off signal for #2 relay
            GPIO.output(self.polarityPins[1], GPIO.HIGH)

            self.polarityNormal = True
        
        print('Done reversing polarities!')
        return self.polarityNormal


    #Cleans Pumps by flushin them for time specified in self.cleanTime
    def cleanPumps(self):
        '''
        for pump in self.pumps:
            GPIO.output(pump, GPIO.LOW)
            time.sleep(self.cleanTime)
            GPIO.output(pump, GPIO.HIGH)
            print('Cleaned Pump ' + str(pump))
        '''

        print('Cleaning pumps!')
        for pump in self.pumps:
            GPIO.output(pump, GPIO.LOW)

        time.sleep(self.cleanTime)

        for pump in self.pumps:
            GPIO.output(pump, GPIO.HIGH)


    def setupButtons(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(23, GPIO.OUT)
        GPIO.output(23, GPIO.HIGH)

        GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        while True:
            try:
                '''
                if (GPIO.input(24) == GPIO.HIGH):
                    print('This GPIO was triggered')
                    self.makeCocktail('vodka shot')
                '''
            except KeyboardInterrupt:
                break

    
    def setMode(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        time.sleep(0.25)
        pinInput = GPIO.input(12)
        print('Mode Input: ' + str(pinInput))
        if(pinInput != 0):
            self.mode = 0
        else:
            self.mode = 1

    def adjustVolumeData(self, ingredientName, shotAmount):
        print('Value: ' + self.pumpFull[ingredientName]['volume'])
        newVal = int(self.pumpFull[ingredientName]['volume']) - (self.shotVolume*shotAmount)
        print('New Value: ' + str(newVal))
        self.pumpFull[ingredientName]['volume'] = str(newVal)
        self.writePumpData()

    
    def canMakeCocktail(self, name):
        cocktailNum = self.cocktailNumbers[name]
        i = 0
        for ingredient in self.cocktailIngredients[cocktailNum]:
            availableAmt = int(self.pumpFull[ingredient]['volume'])
            needAmt = int(self.cocktailAmounts[cocktailNum][i])*self.shotVolume
            print('Ingredient: ' + name + '   availableAmt: ' + str(availableAmt) + '   needAmt: ' + str(needAmt))
            if((availableAmt - needAmt) < 0):
                return False
        return True

    
    def getIngredients(self, name):
        cocktailNum = self.cocktailNumbers[name]
        retIngredients = {}
        i = 0
        for ingredient in self.cocktailIngredients[cocktailNum]:
            retIngredients[ingredient] = self.cocktailAmounts[cocktailNum][i]
            i += 1
        
        return retIngredients

    def getBottlePercentage(self, bottleNum):
        try:
            bottleName = self.pumpNumbers[bottleNum]
            now = int(self.pumpFull[bottleName]['volume'])
            full = int(self.pumpFull[bottleName]['originalVolume'])
            percent = (now/full)*100
            return str(int(percent))
        except Exception as e:
            print(e)
            return 'N/A'

    def getBottleName(self, bottleNum):
        try:
            bottleName = self.pumpNumbers[bottleNum]
            print(bottleName)
            return bottleName
        except Exception as e:
            print(e)
            return 'N/A'

    def writePumpData(self):
        with open('pumpMap.json', 'w') as file:
            json.dump(self.pumpFull, file)
        

'''
if __name__ == '__main__':
    main = Main()
    GPIO.cleanup()
    print('Done')
'''