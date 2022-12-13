# RADx Data Dictionary Specification

A RADx data dictionary is a Comma Separated Values (CSV) file that describes how data contained in another CSV file is structured.  A Comma Separated File represents a grid or table with rows and columns.   The first row of a CSV file is typically a __header__ row that contains __column identifiers__ (or ids for short) for columns.  We some times refer to rows and columns by their zero-based indexes.

The following table shows a CSV containing some example _data_ that contains two columns and three rows.  The first column (index 0) has a column identifier, or column id, of *Participant_Id* and the second column (index 1) has a column identifier of *SampleType*.

The actual data (records) is provided in the rows that follow the header row.

| Participant_Id | SampleType |
|-------|------------|
| P27   | Blood      |
| P35   | Saliva     |

While desirable, not all datafiles have header rows.  In these cases, the first row contains a data record, for example,

|-------|------------|
| P27   | Blood      |
| P35   | Saliva     |

## CSV Format


## Template

While the format of a published RADx Data Dictionary MUST be CSV, tools like Google Sheets or Excel can be used for editing/producing the CSV file.  A Google Sheet template data dictionary may be found [here](https://docs.google.com/spreadsheets/d/1f5KcnCx7fEHcC8uSS5CB71-D-y51BDxFfGltSbj85iw/edit?usp=sharing).


## Layout

A data dictionary CSV file contains a header row plus _one row for each column_ in a target datafile (a row in a data dictionary describes a column in a data file).  Thus, if a datafile has five columns in it (corresponding to five variables), the data dictionary for that datafile will contain _six_ rows – one header row plus five further non-header rows that describe the five columns.

### Data Dictionary Row Ordering

The ordering of rows in a data dictionary is SIGNIFICANT.  The ordering of rows in a data dictionary must correspond to the ordering columns in a target datafile.  Thus, the first non-header row in a data dictionary file describes the first column in a target datafile, the second non-header row in a data dictionary describes the second column in a datafile, and so on.

### Data Dictionary Columns

The data dictionary header row contains the following strings that identify columns in the data dictionary:  

[Id](#column-id), [Label](#column-label), [Required](#column-required), [Datatype](#column-datatype), [Pattern](#column-pattern), [Units](#column-units), [Enumeration](#column-enumeration), [Notes](#column-notes).

These data dictionary columns are described in more detail below.


## Data Dictionary Columns Specification

Each row in a data dictionary MUST contain the following columns.  Since columns are identified by column headers the ordering of these columns is not significant.  However, we recommend that the ordering specified here is followed for the purposes of clarity.  If necessary, susequent columns may be appended to a data dictionary row to support the preservation of extra information that is not provided for by the columns here.

### Column: Id

The `Id` column contains a column identifier for the datafile column being described.  Column identifiers are strings.  To cater for pre-existing RADx study data we do not impose any restrictions on the format or characters that make up a column identifier.  Column identifiers may, for example, contain spaces.

For a given row, the value in this column is REQUIRED and MUST NOT be empty.

### Column: Label

The `Label` column contains a presentation label for the datafile column being described.  Labels are strings and they are usually a human readable form of the [Id](#column-id) column.   In the case where data represents the response to survery questions, the label is typically equal to the text of the question that was asked.

For a given row, the value of this column is OPTIONAL but recommended.

### Column: Required

The `Required` column specifies whether a datafile value is required and may contain `true`, `false` or be empty.  If, for a given datafile column, datafile values are specified as being required then a non-empty value MUST be specified for values in the datafile column.

For a given row, the value of this column is OPTIONAL.  An empty value is the same as a `false` value.

### Column: Datatype

The `Datatype` column contains a datatype name.  Possible values are drawn from the set of [XML schema datatype](https://www.w3.org/TR/xmlschema-2/) names extended with a few datatype names that cover US date formats that are present in RADx data and also ontology terms.  We use XML Schema Datatypes because this a set of datatypes with precisely defined syntax and semantics.  

If an enumeration is supplied to provide a list of controlled values the the data type should be set as the datatype of the values in the enumeration.  See the description of [Column: Enumeration](#column-enumeration).

For a given row the value of this column is REQUIRED and MUST NOT be empty.

#### Common Datatype Names

The following are the most common XML schema datatype names:  

| Datatype Name | Brief Description |
| -- | -- |
[integer](https://www.w3.org/TR/xmlschema-2/#integer) | integer has a lexical representation consisting of a finite-length sequence of decimal digits (#x30-#x39) with an optional leading sign. If the sign is omitted, "+" is assumed. For example: -1, 0, 12678967543233, +100000.
[float](https://www.w3.org/TR/xmlschema-2/#float) | float values have a lexical representation consisting of a mantissa followed, optionally, by the character "E" or "e", followed by an exponent. The exponent must be an integer. The mantissa must be a decimal number. If the "E" or "e" and the following exponent are omitted, an exponent value of 0 is assumed. The special values positive and negative infinity and not-a-number have lexical representations INF, -INF and NaN, respectively. Lexical representations for zero may take a positive or negative sign.  For example, -1E4, 1267.43233E12, 12.78e-2, 12 , -0, 0 and INF are all legal literals for float.
[double](https://www.w3.org/TR/xmlschema-2/#double) | double values have a lexical representaton that is the same as float.
[boolean](https://www.w3.org/TR/xmlschema-2/#boolean) | boolean values can have the following legal literals, true, false, 1, 0
[string](https://www.w3.org/TR/xmlschema-2/#string) | string values are finite sequences of character
[decimal](https://www.w3.org/TR/xmlschema-2/#decimal) | decimal has a lexical representation consisting of a finite-length sequence of decimal digits (#x30-#x39) separated by a period as a decimal indicator. An optional leading sign is allowed. If the sign is omitted, "+" is assumed. Leading and trailing zeroes are optional. If the fractional part is zero, the period and following zero(es) can be omitted. For example: -1.23, 12678967.543233, +100000.00, 210.
[dateTime](https://www.w3.org/TR/xmlschema-2/#dateTime) | dateTime has a lexical representation that consists of finite-length sequences of characters of the form: `'-'? yyyy '-' mm '-' dd 'T' hh ':' mm ':' ss ('.' s+)? (zzzzzz)?`.  For example, 2002-10-10T12:00:00-05:00 (noon on 10 October 2002, Central Daylight Savings Time as well as Eastern Standard Time in the U.S.) is 2002-10-10T17:00:00Z, five hours later than 2002-10-10T12:00:00Z.
[date](https://www.w3.org/TR/xmlschema-2/#date) | The lexical space of date consists of finite-length sequences of characters of the form: `'-'? yyyy '-' mm '-' dd zzzzzz?`.  
[time](https://www.w3.org/TR/xmlschema-2/#time) | The lexical representation for time is the left truncated lexical representation for dateTime: `hh:mm:ss.sss` with optional following time zone indicator. For example, to indicate 1:20 pm for Eastern Standard Time which is 5 hours behind Coordinated Universal Time (UTC), one would write: 13:20:00-05:00.

The set of allowable datatype names also includes the following.  These map to well-defined XML schema datatypes as follows:

| Datatype Name | Lexical Format | Comments | XML Schema Datatype Name | Lexical Format |
| -- | -- | -- | -- | -- |
date_mdy | mm/dd/yyyy | US formatted date with slashes | Date | yyyy-mm-dd
date_dmy | dd/mm/yyy  | International formatted date with slashes | date | yyyy-mm-dd
timestamp | `[0-9]+` | A long integer number that represents a Unix timestamp | long | `[0-9]+` 

### Column: Pattern

The `Pattern` column may contain a regular expression that specifies a pattern that must be matched by datafile values.  For a given datafile value, the complete value must match the pattern.

For a given row the value of this column is OPTIONAL.

### Column: Units

The `Units` column describes represent quantities then the value of this column may be used to document the quantity units.

For a given row, the value of this column is OPTIONAL.

Since there is no standardized list of units used for RADx studies we do not provide a controlled list of units here.  However, here are some common units that we have observed being used in RADx data dictionaries.

| Unit | Abbreviation | Dimension |
| -- | -- | -- |
millimeters | mm | length
metres | m | length
inches | in | length
feet | ft | length
seconds | s | time
hours | hr | time
days | d | time
weeks | w | time
celcius | C | temperature
faranheit | F | temperature
kelvin | K | temperature
milligrams | mg | mass
grams | g | mass
kilograms | kg| mass
pounds | lbs | mass
mols / litre | ml / l | concentration

We recommend that, where possible, SI units are used.

### Column: Enumeration

The `Enumeration` column specifies a controlled list of values that datafile values must be drawn from.  The list is specified as `value0=label0 ; value1=label1 ; ... ; valueN=labelN`. Each item in the list is a value-label pair, separated by a semi-colon character (;).  This pair is written out in the format `value=label`.  

White space surrounding the semi-colon (;) and equals (=) characters is not significant.  Thus, the following are valid examples and are equivalent: 

`0=Saliva ; 1=Blood`

`0=Saliva;1=Blood`

`0 = Saliva ; 1 = Blood`

The above examples use integers as the values but values may be other types of numbers, strings, dateTimes etc.  For example, 

`Saliva=Saliva ; Blood=Blood` (Values and labels are the same string)

`RBC = Red Blood Cells ; WBC = White Blood Cells` (Values are an abbreviation of the string).

Datafiles contain the `value` part of the pairs.  For example, `RBC`, `WBC`, `0`, `1` etc.

### Column: Notes

The `Notes` column may be used to store annotations, notes, comments on the row in the data dictionary and the corresponding column in the datafile. 