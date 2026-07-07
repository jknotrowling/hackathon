from warehouse import Warehouse

wh = Warehouse()  # kommt vorbefüllt
counts = wh.expected_counts()  # {'BEAM-STL-200': 6, ...}  <- Soll
print(counts)
report = wh.reconcile({"BEAM-STL-200": 4})  # <- Zählung aus dem VLM
# jede Zeile: {sku, name, expecteprid, counted, diff, status}
