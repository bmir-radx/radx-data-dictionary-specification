# RADx Data Dictionary Specification

## Introduction

A data dictionary is a form of _metadata_ that describes _data_.  No matter what the concrete serialization format may be, we assume that data is essentially a list of _records_ that contain _fields_.  A field comprises a _field identifier and a _field value_.   

When data is stored in a tabular Comma Separated Values (CSV) file format, records are stored in _rows_, and fields are stored as cells within the rows.   The first row typically represents a _header record_ that contains field identifiers.  For a given column, the field identifier in the header record essentially "names" the fields that are contained within that column.

The table below shows an example CSV file that contains some data.  The data contains two records (orange boxes) made up of seven fields (blue boxes).   In this example, the field identifiers are:  `PartId`, `Date`, `Time`, `Age`, `Mental Status`, `FS LL`, and `FS RL`.  Thus, the 4th column contains `Age` fields.  In the first record (second row) the `Age` field has a field value of `67`.  In the second record (third row), the `FS RL` field value does not have a value and we say that this field is _blank_.

Though not all datafiles have header records, we expect RADx datafiles to have header records.

![Records, Fields and Field Values](schematic.png)

## RADx Data Dictionaries

A RADx _data dictionary_ is a Comma Separated Values (CSV) file that describes how RADx _data_ contained in another CSV file, a _datafile_, is structured.  A data dictionary CSV file contains EXACTLY ONE data dictionary.

## Data Dictionary CSV Format

Data dictionaries MUST use the CSV format specified by [RFC 4180](https://datatracker.ietf.org/doc/html/rfc4180#page-2).  

Data dictionaries may be created with tools such as Google Sheets or Microsoft Excel.  Both of these tools produce CSV files in accordance with this specification.  When saving a CSV file in Microsoft Excel be sure to choose the "CSV UTF-8 (Comma delimited) (.CSV)" file format.

## Data Dictionary Layout

A data dictionary contains a list of records, represented as rows, that describe the sequence of fields in a target datafile.  There is exactly one data dictionary record per datafile field. 

A data dictionary CSV file contains a header record plus _one record for each of the target datafile's fields_.  Since the target datafile's fields are in columns, this means a record in a data dictionary essentially describes a column in the target data file.  Thus, if the target datafile has five columns in it, the data dictionary will contain _six_ records – one header record plus five non-header records that describe the five datafile fields.

 Each data dictionary record describes the particular features, or attributes, of the target datafile field that it represents.  For example, taking the `PartId` field in the above datafile, the data dictionary would describe this field as having an identifier of `PartId`, having field-values that have a datatype of `string` and a pattern of `^[NP](\d+)$`, and requiring a non-blank value.

Each record in a data dictionary has the same number of fields.  In other words, each record has the same length, or each row the same number of columns.
 
### Data Dictionary Row Ordering

The ordering of records in a data dictionary is SIGNIFICANT.  The sequence of records in a data dictionary MUST correspond to the sequence of fields in the target datafile.  Thus, the first non-header record in a data dictionary file describes the first field in the target datafile, the second non-header record in a data dictionary describes the second field in a datafile, and so on. 

While the Id of a data dictionary record SHOULD match the target datafile Field Id, it is the sequence order of data dictionary records that is matched to the sequence order of data file fields.

### Data Dictionary Fields

A data dictionary header record contains the following sequence of strings as its field identifiers:

[Id](#field-id), [Label](#field-label), [Required](#field-required), [Datatype](#field-datatype), [Pattern](#field-pattern), [Units](#field-units), [Enumeration](#field-enumeration), [Notes](#field-notes).

These data dictionary columns are described in more detail below. 

Since columns are identified by column headers the ordering of these columns is not significant.  However, for maximum interoperability and ease of use, we strongly recommend following the ordering specified here.  

If necessary, susequent fields/columns may be appended to a data dictionary to support the preservation of extra information that is not provided for by the columns here.

## Data Dictionary Fields Specification

Each record in a data dictionary MUST contain the following, possibly empty, fields.  For each field, the *Value Status* specifies whether a non-blank value is required or whether a blank value is acceptable.

### Field: Id

__Value Status__: REQUIRED (the value for the `Id` field MUST NOT be empty)

The `Id` field in the data dictionary specifies an identifier for the datafile field being described.  Datafile field identifiers are strings.  To cater for pre-existing RADx study data we do not impose any restrictions on the format or characters that make up a field identifier.  Field identifiers may contain spaces.

Note: In RADx harmonized data, the Id typically begins with `nih_`, reflecting the NIH field name assigned to RADx harmonized fields (and corresponding Common Data Elements).

### Field: Label

__Value Status__: RECOMMENDED 

The `Label` field in the data dictionary specifies a presentation label for the datafile field being described.  Labels are strings; they may be a human readable form of the [Id](#field-id).   In the case where data represents the response to survery questions, the label is often the text of the question that was asked.

Because the Label can be used in many presentations of RADx data, it would not be unusual for entries without a Label to cause issues in some software. 

### Field: Required

__Value Status__: OPTIONAL

__Default Value__: FALSE

The `Required` field in the data dictionary specifies whether a datafile value must be present. The Required value itself may contain `TRUE`, `FALSE` or be empty.  An empty value is considered to be FALSE. If, for a given datafile field, datafile values are specified as being required (TRUE), then a non-empty value MUST be specified for all values in that datafile field.  

The values for the data dictionary's Required field are case insensitive: "True", "true" and "TRUE" all map to boolean `TRUE`.

For a given row, the value of this field is OPTIONAL.  An empty value is the same as a `FALSE` value.

### Field: Datatype

__Value Status__: REQUIRED (the value MUST NOT be empty)

The `Datatype` field in the data dictionary specifies a datatype name that types field values.  Possible datatype names are drawn from the set of [XML schema datatype](https://www.w3.org/TR/xmlschema-2/) names, extended with a few datatype names that cover US date formats that are present in RADx data and also ontology terms (see below).  We use XML Schema Datatypes because this set of datatypes has precisely defined syntax and semantics.  

If an enumeration is supplied to provide a list of controlled values, then the datatype name should be set as the datatype name of the values in the enumeration.  See the description of [Column: Enumeration](#field-enumeration).  For example, if an enumeration of `0 = Blood ; 1 = Saliva` was specified for a field the datatype name for this field would be `integer`, since the values of this enumeration are integers.  Similarly, if an enumeration of `RBC = Red Blood Cells; WBC = White Blood Cells` is specified for a field then the datatype name for that field would be `string`, since the values of this enumeration are strings.

Datatype names are case insensitive, thus `Integer` and `integer` mean the same thing.

#### Field Datatype Names

The following are the most common XML schema datatype names.  For each datatype name we provide a brief description of the valid lexical form for the datatype.  For more precise details follow the relevant datatype link to the XML schema datatypes specification.  

| Datatype Name | Brief Description |
| -- | -- |
[integer](https://www.w3.org/TR/xmlschema-2/#integer) | integer has a lexical representation consisting of a finite-length sequence of decimal digits (#x30-#x39) with an optional leading sign. If the sign is omitted, "+" is assumed. For example: -1, 0, 12678967543233, +100000.
[float](https://www.w3.org/TR/xmlschema-2/#float) | float values have a lexical representation consisting of a mantissa followed, optionally, by the character "E" or "e", followed by an exponent. The exponent must be an integer. The mantissa must be a decimal number. If the "E" or "e" and the following exponent are omitted, an exponent value of 0 is assumed. The special values positive and negative infinity and not-a-number have lexical representations INF, -INF and NaN, respectively. Lexical representations for zero may take a positive or negative sign.  For example, -1E4, 1267.43233E12, 12.78e-2, 12 , -0, 0 and INF are all legal literals for float.
[double](https://www.w3.org/TR/xmlschema-2/#double) | double values have a lexical representaton that is the same as float.
[boolean](https://www.w3.org/TR/xmlschema-2/#boolean) | boolean values can have the following legal literals, true, false, 1, 0
[string](https://www.w3.org/TR/xmlschema-2/#string) | string values are finite sequences of characters; this is the datatype to use if none of the other datatypes are appropriate.
[decimal](https://www.w3.org/TR/xmlschema-2/#decimal) | decimal has a lexical representation consisting of a finite-length sequence of decimal digits (#x30-#x39) separated by a period as a decimal indicator. An optional leading sign is allowed. If the sign is omitted, "+" is assumed. Leading and trailing zeroes are optional. If the fractional part is zero, the period and following zero(es) can be omitted. For example: -1.23, 12678967.543233, +100000.00, 210.
[dateTime](https://www.w3.org/TR/xmlschema-2/#dateTime) | dateTime has a lexical representation that consists of finite-length sequences of characters of the form: `'-'? yyyy '-' mm '-' dd 'T' hh ':' mm ':' ss ('.' s+)? (zzzzzz)?`.  For example, 2002-10-10T12:00:00-05:00 (noon on 10 October 2002, Central Daylight Savings Time or Eastern Standard Time in the U.S.) is 2002-10-10T17:00:00Z, five hours later than 2002-10-10T12:00:00Z.
[date](https://www.w3.org/TR/xmlschema-2/#date) | The lexical space of date consists of finite-length sequences of characters of the form: `'-'? yyyy '-' mm '-' dd zzzzzz?`.  
[time](https://www.w3.org/TR/xmlschema-2/#time) | The lexical representation for time is the left truncated lexical representation for dateTime: `hh:mm:ss.sss` with optional following time zone indicator. For example, to indicate 1:20 pm for Eastern Standard Time which is 5 hours behind Coordinated Universal Time (UTC), one would write: 13:20:00-05:00.

The set of allowable datatype names also includes the following.  These map to well-defined XML schema datatypes as follows:

| Datatype Name | Lexical Format | Comments | XML Schema Datatype Name | Lexical Format |
| -- | -- | -- | -- | -- |
date_mdy | mm/dd/yyyy | US-formatted date with slashes | date | yyyy-mm-dd
date_dmy | dd/mm/yyy  | International-formatted date with slashes | date | yyyy-mm-dd
timestamp | `[0-9]+` | A long integer number that represents a Unix timestamp | long | `[0-9]+` 

### Field: Pattern

__Value Status__: OPTIONAL

The `Pattern` field in the data dictionary may contain a regular expression that specifies a pattern that must be matched by datafile values.  For a given datafile value, the complete value must match the pattern.

### Field: Units

__Value Status__: OPTIONAL

The `Units` field in the data dictionary describes represent quantities then the value of this field may be used to document the quantity units.

Since there is no standardized list of units used for RADx studies we do not provide a controlled list of units here.  However, here are some common units that we have observed being used in RADx data dictionaries.

| Unit | Abbreviation | Dimension |
| -- | -- | -- |
millimeter | mm | length
meter | m | length
inch | in | length
foot | ft | length
second | s | time
hour | hr | time
day | d | time
week | w | time
Celsius degree | C | temperature
Fahrenheit degree | F | temperature
Kelvin degree | K | temperature
milligram | mg | mass
gram | g | mass
kilogram | kg | mass
pound | lbs | mass
mole per litre | ml/l | concentration

We recommend that, where possible, SI units and abbreviations are used.

### Field: Enumeration

__Value Status__: OPTIONAL

The `Enumeration` field in the data dictionary specifies a controlled list of values that datafile values must be drawn from.  The list is specified as `value0=label0 ; value1=label1 ; ... ; valueN=labelN`. Each item in the list is a value-label pair, written in the format`value=label`, and separated from surrounding items by a semi-colon character (;).   

White space surrounding the semi-colon (;) and equals (=) characters is not significant.  Thus, the following are valid examples and are equivalent: 

`0=Saliva ; 1=Blood`

`0=Saliva;1=Blood`

`0 = Saliva ; 1 = Blood`

The above examples use integers as the values but values may be other datatypes: numbers, strings, dateTimes, etc.  For example, 

`Saliva=Saliva , Blood=Blood` (Values and labels are the same string)

`RBC = Red Blood Cells , WBC = White Blood Cells` (Values are an abbreviation of or a code for the string).

Note that the target datafile would contain the `value` part of the pairs.  For example, `RBC`, `WBC`, `0`, `1` etc.

### Field: Notes

__Value Status__: OPTIONAL

The `Notes` field in the data description may be used to store annotations, notes, comments on the row in the data dictionary and the corresponding field in the datafile.  The values of this field are for human use and are not parsed to be used in a computational way.

## Template

While the format of a published RADx Data Dictionary MUST be CSV, tools like Google Sheets or Excel can be used for editing/producing the CSV file.  A Google Sheet template data dictionary may be found [here](https://docs.google.com/spreadsheets/d/1f5KcnCx7fEHcC8uSS5CB71-D-y51BDxFfGltSbj85iw/edit?usp=sharing).
