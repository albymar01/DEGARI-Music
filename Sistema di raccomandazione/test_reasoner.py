from owlready2 import *
onto = get_ontology("http://test.org/onto.owl")
with onto:
    class A(Thing): pass
sync_reasoner(debug=2)
print("REASONER OK")
