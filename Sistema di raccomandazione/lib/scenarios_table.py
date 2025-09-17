import sys
import os

lib_dir = os.path.dirname(__file__)
sys.path.append(lib_dir)

import ontology_manager as om


# creates a table with a row for each scenario,
# computing the probablility of each row
# and excluding trivial scenarios
class Table:
    
    def __init__(self, from_input, max_attrs):
        #  create a "truth table" of for each scenario (1 = true)
        self.data = from_input
        self.table = self.create_table(max_attrs)

        #  add a column for the probability of the scenario and sort the table over it
        self.add_percentage()
        self.table.sort(reverse = True, key = lambda row : row[-1])

    # initialize table excluding invalid scenarios
    def create_table(self, max_attrs):
        n_of_cols = len(self.data.typical_attrs)
        min_attrs = 1
        max_attrs = min(n_of_cols - 1, max_attrs)
        
        rows = list()
        
        # check for conflicts between rigid properties that would invalid every combination
        if self.rigid_conflict():
            return rows

        for i in range(pow(2, len(self.data.typical_attrs))):
            bin_row = self.to_binary(i, n_of_cols)

            # count number of properties selected overall and from the head concept
            n_sel = 0
            n_sel_from_h = 0
            n_sel_from_m = 0
            h_count = 0
            for bit_index in range(len(bin_row)):
                n_sel += bin_row[bit_index]
                #if bit belongs_to_head
                if self.data.typical_attrs[bit_index][2]:
                    n_sel_from_h += bin_row[bit_index]
                    h_count += 1
                else:
                    n_sel_from_m += bin_row[bit_index]

            # check the following conditions on the scenario:
            # (1) scenarios selecting no properties are not allowed
            # (2) scanarios selecting all properties are not allowed
            # (3) scanarios selecting all head properties are not allowed
            # (4) scanarios selecting less than one property per part are not allowed
            if n_sel >= min_attrs and n_sel <= max_attrs \
                                  and n_sel_from_h < h_count \
                                  and min(n_sel_from_h, n_sel_from_m) >= 1:
                # check if the selected typical properties conflict with rigid properties
                if not self.typical_rigid_conflict(bin_row):
                    rows.append(bin_row)

        return rows
    
    # check for conflicts between rigid properties
    def rigid_conflict(self):
        # if any rigid property is in both positive and negative lists, there is a conflict
        for p in self.data.rigid_pos_list:
            if p in self.data.rigid_neg_list:
                return True
        # if no conflicts found, return False
        return False
    
    # check for conflicts between the typical properties in a scenario and the rigid properties
    def typical_rigid_conflict(self, scenario):
        # for each typical property
        for i in range(len(self.data.typical_attrs)):
            # if the property is selected in scenario
            if scenario[i] == 1:
                prop = self.data.typical_attrs[i][0]
                # if the property is negated
                if len(prop) > 0 and prop[0] == '-':
                    # check for conflicts with positive rigid properties
                    if prop in self.data.rigid_pos_list:
                        return True
                else:
                    # check for conflicts with negative rigid properties
                    if prop in self.data.rigid_neg_list:
                        return True
        # if no conflicts found, return False
        return False

    # converts num to binary on len bits,
    # returning the list of bits
    def to_binary(self, num, len):
        bin = f'{num:0{len}b}'  #format as a 0-padded, len-width, binary string
        return [int(digit) for digit in bin]    #return list of digits as integers

    # computes the probability of each scenario (i.e. each row)
    def add_percentage(self):
        for line in range(len(self.table)):
            percentage = 100

            for i in range(len(self.table[line])):
                # multiply by p if the property is chosen in the scenario, by 1-p otherwise
                if (self.table[line][i] == 1):
                    percentage *= self.data.typical_attrs[i][1] 
                else:
                    percentage *= 1 - self.data.typical_attrs[i][1]

            self.table[line].append(percentage)

    # checks the validity of a scenario
    def consistent_scenario(self, scenario):
        return self._is_consistent(scenario) and self._prefers_head(scenario)

    # checks that the scenario is consistent
    def _is_consistent(self, scenario):
        onto = om.OntologyManager(self.data.typical_attrs, self.data.attrs, scenario)
        return onto.is_consistent()
    
    # checks that no selected properties from the modifier
    # conflict with any discarded properties of the head
    def _prefers_head(self, scenario):
        row = list(scenario)    #create a modifiable copy of the scenario
        # for each typical attribute in the scenario
        for i in range(len(self.data.typical_attrs)):
            # if it belongs to head
            if self.data.typical_attrs[i][2]:
                # invert its assigned value
                row[i] = 1 - row[i]
        
        # if the resulting ontology is not consistent, there is a conflict
        onto = om.OntologyManager(self.data.typical_attrs, [], row) # Note that here we ingore rigid properties
        return onto.is_consistent()