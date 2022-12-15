# RADx Data Dictionary Specification

A RADx data dictionary is a Comma Separated Values (CSV) file that describes how data contained in another CSV file is structured.  A Comma Separated File represents a grid or table with rows and columns.   The first row of a CSV file is typically a __header__ row that contains __column identifiers__ (or ids for short) for columns.  We sometimes refer to rows and columns by their zero-based indexes.

The following table shows a CSV containing some example _data_ that contains two columns and three rows.  The first column (index 0) has a column identifier, or column id, of *Participant_Id* and the second column (index 1) has a column identifier of *SampleType*.

The actual data (records) are provided in the rows that follow the header row.

| Participant_Id | SampleType |
|-------|------------|
| P27   | Blood      |
| P35   | Saliva     |

Though not all datafiles have header rows, we expect RADx datafiles to have a header row, with the entries in the header row being the variable names for the data in the corresponding columns.

Whereas the datafile has its variable names in the cells of the first row, the data dictionary describes each datafile _variable_ in a separate row, and the columns contain the attributes of the datafile variables. You can think of each row of a data dictionary as a data element that defines a single question about a variable in the datafile.

## CSV Format

Data dictionaries MUST use the CSV format specified by [RFC 4180](https://datatracker.ietf.org/doc/html/rfc4180#page-2).  Data dictionaries may be created with cell-based tools such as Google Sheets or Microsoft Excel.  Both of these tools produce CSV files in accordance with this specification.  When saving a CSV file in Microsoft Excel be sure to choose the "CSV UTF-8 (Comma delimited) (.CSV)" file format.

## Layout

A data dictionary CSV file contains a header row plus _one row for each of the target datafile's data variables_. (Since the datafile's variables are in columns, that means a row in a data dictionary describes a column in a data file.)  Thus, if a datafile has five columns in it (corresponding to five variables), the data dictionary for that datafile will contain _six_ rows – one header row plus five non-header rows that describe the five columns.

### Data Dictionary Row Ordering

The ordering of rows in a data dictionary is SIGNIFICANT.  The order of rows in a data dictionary MUST correspond to the order of columns in a target datafile.  Thus, the first non-header row in a data dictionary file describes the first column in a target datafile, the second non-header row in a data dictionary describes the second column in a datafile, and so on. 

While the Id of the data dictionary row should match the variable name of the datafile column, if the datafile's header row is missing or has mis-matched names, the data dictionary order is used to understand the datafile columns.

### Data Dictionary Columns

The data dictionary header row contains the following strings that identify columns in the data dictionary (click on the name to be taken to a description of that column's values):

[Id](#column-id), [Label](#column-label), [Required](#column-required), [Datatype](#column-datatype), [Pattern](#column-pattern), [Units](#column-units), [Enumeration](#column-enumeration), [Notes](#column-notes).

These data dictionary columns are chosen to match the format used for REDCap data dictionary exports, and the columns are described in more detail below. 

The data dictionary header row may contain additional columns of the user's choosing, to capture richer information about each of the variables described by the data dictionary. We offer some recommended names to use for the most common cases of additional columns.

Since columns are identified by column headers the ordering of these columns is not significant.  However, for maximum interoperability and ease of use, we strongly recommend following the ordering specified here.  If necessary, susequent columns may be appended to a data dictionary row to support the preservation of extra information that is not provided for by the columns here.

## Data Dictionary Columns Specification

Each row in a data dictionary MUST contain the following columns. Depending on the *Value Status* of the column, values may or may not be REQUIRED in that column for every row in the data dictionary

### Column: Id

__Value Status__: REQUIRED (the value for Id MUST NOT be empty)

The `Id` column in the data dictionary contains an identifier for the datafile column being described.  Datafile column identifiers are strings.  To cater for pre-existing RADx study data we do not impose any restrictions on the format or characters that make up a column identifier, except that it may not include a comma, quote, or semi-colon.  Column identifiers may contain spaces, for example.

In RADx harmonized data, the Id typically begins with `nih_`, reflecting the NIH variable name assigned to RADx harmonized variables (and corresponding Common Data Elements).

### Column: Label

__Value Status__: RECOMMENDED 

The `Label` column in the data dictionary contains a presentation label for the datafile column being described.  Labels are strings; they may be a human readable form of the [Id](#column-id).   In the case where data represents the response to survery questions, the label is often the text of the question that was asked.

Because the Label can be used in many presentations of RADx data, it would not be unusual for entries without a Label to cause issues in some software. 

### Column: Required

__Value Status__: OPTIONAL
__Default Value__: FALSE

The `Required` column in the data dictionary specifies whether a datafile value must be present. The Required value itself may contain `TRUE`, `FALSE` or be empty.  An empty value is considered to be FALSE. If, for a given datafile column, datafile values are specified as being required (TRUE), then a non-empty value MUST be specified for all values in that datafile column.  

The values for the data dictionary's Required column are case insensitive: "True", "true" and "TRUE" all map to boolean `TRUE`.

For a given row, the value of this column is OPTIONAL.  An empty value is the same as a `FALSE` value.

### Column: Datatype

__Value Status__: REQUIRED (the value MUST NOT be empty)

The `Datatype` column in the data dictionary contains a datatype name that describes what kind of data is in the datafile column.  Possible values are drawn from the set of [XML schema datatype](https://www.w3.org/TR/xmlschema-2/) names, extended with a few datatype names that cover US date formats that are present in RADx data and also ontology terms (see below).  We use XML Schema Datatypes because this set of datatypes has precisely defined syntax and semantics.  

If an enumeration is supplied to provide a list of controlled values, then the Datatype should be set as the datatype of the values in the enumeration.  See the description of [Column: Enumeration](#column-enumeration).

Values for this column are case insensitive, thus `Integer` and `integer` mean the same thing.

#### Common Datatype Names

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

### Column: Pattern

__Value Status__: OPTIONAL

The `Pattern` column in the data dictionary may contain a regular expression that specifies a pattern that must be matched by datafile values.  For a given datafile value, the complete value must match the pattern.

### Column: Units

__Value Status__: OPTIONAL

The `Units` column in the data dictionary describes represent quantities then the value of this column may be used to document the quantity units.

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

### Column: Enumeration

__Value Status__: OPTIONAL

The `Enumeration` column in the data dictionary specifies a controlled list of values that datafile values must be drawn from.  The list is specified as `value0=label0 , value1=label1 , ... , valueN=labelN`. Each item in the list is a value-label pair, written in the format`value=label`, and separated from surrounding items by a comma character (,).   

White space surrounding the comma (,) and equals (=) characters is not significant.  Thus, the following are valid examples and are equivalent: 

`0=Saliva , 1=Blood`

`0=Saliva,1=Blood`

`0 = Saliva , 1 = Blood`

The above examples use integers as the values but values may be other datatypes: numbers, strings, dateTimes, etc.  For example, 

`Saliva=Saliva , Blood=Blood` (Values and labels are the same string)

`RBC = Red Blood Cells , WBC = White Blood Cells` (Values are an abbreviation of or a cod for the string).

Datafiles contain the `value` part of the pairs.  For example, `RBC`, `WBC`, `0`, `1` etc.

### Column: Notes

__Value Status__: OPTIONAL

The `Notes` column in the data description may be used to store annotations, notes, comments on the row in the data dictionary and the corresponding column in the datafile.  The values of this column are for human use and are not parsed to be used in a computational way.

## Template

While the format of a published RADx Data Dictionary MUST be CSV, tools like Google Sheets or Excel can be used for editing/producing the CSV file.  A Google Sheet template data dictionary may be found [here](https://docs.google.com/spreadsheets/d/1f5KcnCx7fEHcC8uSS5CB71-D-y51BDxFfGltSbj85iw/edit?usp=sharing).
