# DEGARI:  Dynamic Emotion Generator And ReclassIfier

A Python tool for dynamic generation of knowledge in Description Logics of 
Typicality tested in the contexts of RaiPlay, WikiArt Emotions and ArsMeteo

DEGARI is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. The software is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. See http://www.gnu.org/licenses/.

------------------------------------------------------------------------------------------

## Module 1 - Generation of prototypes

- Description: Generation of prototypes of artworks 

- Folder: ./Creazione dei prototipi

- Libraries nltk and treetaggerwrapper are needed (install if missing)

- Input: file containing information about artworks in JSON format

- Output: prototypes of artworks

- CONFIGURATION: specified in prototyper_config.py
	
	- jsonDescrFile: the name of JSON input file
	
	- instanceID: a JSON attribute used in jsonDescrFile as an identifier for the artwork
		(a single artwork may have different instances, such as the episodes of a tv series)
	
	- instanceDescr: a list containing the JSON attributes used to describe an instance
		(used to generate the artwork's prototype)
	
	- outPath: the path of the directory in which the generated prototypes will be saved

- To run the generation of prototypes of artworks: python3 prototyper.py

- Ignore warnings

------------------------------------------------------------------------------------------

## Module 2 - Emotions combination 

- Description: the tool generates the input file for module CoCoS, able to generate novel genres
by combining the prototypes of two existing ones by exploiting the logic TCL.
Generated file will contain all the properties of prototypes of the two starting emotions (HEAD and MODIFIER)

- Folder: ./Sistema di raccomandazione

- CONFIGURATION in cocos_config.py specifies:
    - the folder containing prototypical properties of the existing emotions
    - the folder containing rigid properties of the existing emotions
    - the output folder

- To run the generation of the input file for CoCoS: python3 cocos_preprocessing.py emotion1 emotion2

      Example : python3 cocos_preprocessing.py joy fear

	
- it's suggested to save prototypes for different languages in different directories
	(e.g. "prototipi" contains english version, while "prototipi_it" contains intalian version)
	in order to run the recommendation for one language at a time

------------------------------------------------------------------------------------------

## Module 3 - Combining emotions by exploiting CoCoS

- Description: a novel emotion is obtained by exploiting CoCoS for the combination of two existing emotions

- Folder: ./Sistema di raccomandazione

- To run: python3 cocos.py [prototypeFile]* [maximum number of inherited properties]*

  - *optional, the default is specified in cocos_config.py and allows to run the combination on all the files in a directory

		Example: python3 cocos.py prototipi/joy_fear

- At the end of its execution, the tool CoCoS writes the prototypes of the novel emotion in the suitable file

- Note: to run the reasoning process, you need Java to be installed on your system. If you get an "Unexpected error during reasoning", please check your java installation.

------------------------------------------------------------------------------------------

## Module 4 - Recommender system

- Description: show all the artwork instances that are re-classified in the novel generated emotion.
	Results are presented ordered by a rank of compatibility artwork-novel emotion.
	Each result instance is followed by the explanation of the recommendation.

- Folder: ./Sistema di raccomandazione/Classificatore

- Input
	- JSON description file (may be the same used for Module 1)
	- artwork prototypes files (generated in Module 1)
	- an emotion prototype or a set of emotion prototypes
	
- Output
	- the program prints the recommendations and their explanations
	- if it's run on a set of prototypes, it also generates 2 output files (in .tsv format):
		- recommendations.tsv contains couples "artwork    emotion", representing the resulting recommendations
		- resume.tsv contains couples "emotion    recommendations_number", representing
			the number of recommendations generated for each emotion
			
- CONFIGURATION: specified in Recommender_config.py
	
	- jsonDescrFile: the name of JSON description file
	
	- protPath: the path to the artwork prototypes folder (generated in Module 1)
	
	- instanceID: a JSON attribute used in jsonDescrFile as an identifier for the artwork
		(it MUST correspond to the name of the artwork's prototype file into protPath)
	
	- instanceDescr: a list containing the JSON attributes used to describe an instance
		(used to generate the recommendations)
	
	- instanceTitle: instance title attributes in json description file
		the first attribute should be the artwork instance's title, followed by other main features

- To run recommendation for an emotion prototype: python3 Recommender.py novel_emotion_prototype

      Example: python3 Recommender.py ../prototipi/joy_fear
    
- To run on a set of emotion prototypes saved in a folder: ./Launch_Recommender.sh [folder]
	Example: ./Launch_Recommender.sh ../prototipi_it
	
	- if no folder is specified, the default is "../prototipi"
	- this execution also updates "recommendations.tsv" and "resume.tsv", and
		at the end prints the overall number of artworks involved by the recommendations
