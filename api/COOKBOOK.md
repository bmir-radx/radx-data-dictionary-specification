# Data Dictionary API Cookbook

Task-oriented recipes for `dd_api`, written for a first-time user. Every
recipe is a complete, pasteable program.

The recipes share this small dictionary. Paste it once at the top of your
session (or save it as `demo.csv` and use `DataDictionary.load("demo.csv")`):

```python
import io
from dd_api import DataDictionary

DEMO = io.StringIO(
    "Id,Label,Datatype,Section,Unit,Enumeration,MissingValueCodes,Terms\n"
    "age,Age in years,integer,Demographics,,,,\n"
    'sex,Sex at birth,integer,Demographics,,"""0""=[Female] | ""1""=[Male]","""-9096""=[Refused]",\n'
    "weight,Body weight,decimal,Vitals,kg,,,\n"
    "heart_rate,Heart rate,integer,Vitals,,,,http://purl.obolibrary.org/obo/NCIT_C49677\n"
)

dd = DataDictionary.load(DEMO)
```

---

## 1. Load a dictionary and see what's in it

```python
print(dd)              # DataDictionary(4 elements)
print(dd.ids)          # ('age', 'sex', 'weight', 'heart_rate')
print(dd.sections)     # ('Demographics', 'Vitals')
```

## 2. Look at one field

```python
element = dd["weight"]
print(element.label)      # Body weight
print(element.datatype)   # decimal
print(element.unit)       # kg
```

If you are not sure the field exists, use `get`, which returns `None`
instead of raising:

```python
if dd.get("bmi") is None:
    print("no bmi field")   # no bmi field
```

## 3. Find every enumerated field and print its choices

```python
for element in dd:
    if element.is_enumerated:
        print(element.id)
        for choice in element.enumeration:
            print(f"  {choice.value} = {choice.label}")

# sex
#   0 = Female
#   1 = Male
```

## 4. See which codes mean "no data"

```python
for element in dd:
    for code in element.missing_value_codes:
        print(f"{element.id}: {code.value} means {code.label!r}")

# sex: -9096 means 'Refused'
```

## 5. Walk the dictionary section by section

```python
for section in dd.sections:
    print(section)
    for element in dd.elements_in_section(section):
        print(f"  {element.id}: {element.label}")

# Demographics
#   age: Age in years
#   sex: Sex at birth
# Vitals
#   weight: Body weight
#   heart_rate: Heart rate
```

## 6. Find fields annotated with ontology terms

```python
for element in dd:
    for term in element.terms:
        print(element.id, "->", term)

# heart_rate -> http://purl.obolibrary.org/obo/NCIT_C49677
```

## 7. Resolve units to UCUM codes

`element.unit` is the text exactly as written; `element.resolved_unit` is the
structured unit when the toolkit recognises it:

```python
for element in dd:
    if element.resolved_unit:
        u = element.resolved_unit
        print(f"{element.id}: {u.descriptive_name} (UCUM {u.ucum_code})")

# weight: kilogram (UCUM kg)
```

## 8. Convert to a LinkML schema — and back

```python
schema_yaml = dd.to_linkml()          # same output as the dd-to-linkml command
reloaded = DataDictionary.from_linkml(io.StringIO(schema_yaml))
print(reloaded.ids == dd.ids)         # True
```

`from_linkml` also reads hand-written LinkML schemas (fields as
`attributes:` or `slots:` + `slot_usage:`, enumerations inline or named) —
see its docstring for what can and cannot be recovered.

## 9. Build a dictionary from scratch and write it out

You do not need a CSV file to start from — build elements in code and
serialise them:

```python
from dd_api import DataDictionary, DataElement, EnumItem

dd = DataDictionary([
    DataElement(id="visit", label="Visit number", datatype="integer"),
    DataElement(
        id="consented",
        label="Consent given",
        datatype="integer",
        enumeration=(EnumItem(value="0", label="No"), EnumItem(value="1", label="Yes")),
    ),
])
print(dd.to_csv())

# Id,Aliases,Label,Description,Section,Cardinality,Terms,Datatype,...
# visit,,Visit number,,,single,,integer,,,,,,,,
# consented,,Consent given,,,single,,integer,,,"""0""=[No] | ""1""=[Yes]",,,,,
```

## 10. Handle a bad dictionary gracefully

Loading is fail-fast: the first problem raises `ReadError` with a clear
message. Catch it if you want to report rather than crash:

```python
from dd_api import DataDictionary, ReadError

bad = io.StringIO("Id,Label,Datatype\npulse,Pulse,Integer\n")   # miscased datatype
try:
    DataDictionary.load(bad)
except ReadError as error:
    print(f"not a valid dictionary: {error}")

# not a valid dictionary: Line 2: Unknown datatype name 'Integer'. ...
```

To see *every* problem in a file rather than the first one, use the sibling
[validator](../validator/) (`dd-validate my_dictionary.csv`) — that is its
job, and it prints all findings with line numbers and severities.
