# Selectra

[Русская версия](GLOSSARY.ru.md)

The language of selecting similar edges and faces by example within an explicitly defined assembly scope.

**Search scope**:
The body, the selected component instance's hierarchy, or the entire visible assembly. The canonical semantics of This Body / This Component / All Components are in [UX.md](docs/UX.md).

## Terms

**Example**:
An edge or face explicitly shown by the user as part of the desired selection. An element found by the tool does not itself become an example.

**Exclusion**:
An element the user explicitly marked as unwanted. It constrains the result and helps distinguish possible intents.

**Intent**:
A hypothesis about which property or geometric relationship the user regards as the basis for similarity.
_Avoid_: user confidence, true intent

**Shape analogue**:
An element with matching shape and size, allowing translation, rotation or reflection within the specified tolerance. Equal perimeter alone does not make elements shape analogues.

**Wall pair**:
Two faces on opposite sides of one local wall of a body. Parallelism or proximity alone does not establish this relationship.

**Feature repetition**:
Several portions of geometry with a common structure and size, positioned by a repeated transformation.

**Similarity level**:
A group of equally justified candidates in a fixed selection-expansion order. A level does not mean a number of transitions between adjacent faces.

**Selection range**:
The examples and all included similarity levels, minus exclusions.

**Selection explanation**:
A short, verifiable reason for including an element, such as the same shape or the inner side of the example wall.
