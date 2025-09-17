# Builds a COCOS input file from the prototypes of two concepts in input

import cocos_config as cfg
import sys
import os


# returns a dict containing the typical properties read from the specified path
def getTypicalProperties(path_file) :    
    prop_dict = dict()

    if os.path.exists(path_file):
        with open(path_file) as f:
            for p in f.readlines():
                prop = p.split(':')
                value = float(prop[1].strip())
                prop_dict[prop[0]] = round(value, 3)

    return prop_dict

# returns a list containing the rigid properties read from the specified path
def getRigidProperties(path_file) :    
    prop_list = list()

    if os.path.exists(path_file):
        with open(path_file) as f:
            for p in f.readlines():
                prop_list.append(p.strip())

    return prop_list

# write the input file for COCOS
def write_cocos_file(head, modifier):
    with open(f'{cfg.COCOS_DIR}/{head}_{modifier}.txt', "w") as f:
        f.write(f'Title: {head}-{modifier}\n\n')
        f.write(f'Head Concept Name: {head}\n')
        f.write(f'Modifier Concept Name: {modifier}\n\n')
    
        # rigid properties
        for p in getRigidProperties(f'{cfg.RIGID_PROP_DIR}/{head}.txt'):
            f.write(f"head, {p}\n")
        f.write("\n")
        
        for p in getRigidProperties(f'{cfg.RIGID_PROP_DIR}/{modifier}.txt'):
            f.write(f"modifier, {p}\n")
        f.write("\n")
        
        # typical properties
        modifier_typ = getTypicalProperties(f'{cfg.TYPICAL_PROP_DIR}/{modifier}.txt')
        for p in modifier_typ:
            f.write(f'T(modifier), {p}, {modifier_typ[p]}\n')
        f.write("\n")
        
        head_typ = getTypicalProperties(f'{cfg.TYPICAL_PROP_DIR}/{head}.txt')
        for p in head_typ:
            f.write(f'T(head), {p}, {head_typ[p]}\n')
        f.write("\n")



if __name__ == '__main__' :
    head = ""
    modifier = ""

    # read parameters
    if len(sys.argv) == 3:
        head = sys.argv[1]
        modifier = sys.argv[2]
            
        write_cocos_file(head, modifier)
    else:
        print("Running all possible combinations...")
        print("To run a specific combination: python3 cocos_preprocessing.py <head_concept> <modifier_concept>\n")
        file_list = os.listdir(cfg.TYPICAL_PROP_DIR)
        for f1 in file_list:
            for f2 in file_list:
                if f1 != f2:
                    write_cocos_file(f1.split(".")[0], f2.split(".")[0])