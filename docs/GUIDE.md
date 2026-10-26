# Selectra user guide

**English** · [Русский](GUIDE.ru.md)

Selectra builds selections from examples and closed contours. Its commands appear in the Fusion context menu when BRep edges or faces are selected.

| Task | Command |
| --- | --- |
| Find matching edges, faces, or face groups | **Select Similar** |
| Select a closed edge loop | **Select Chain** |
| Follow the inside walls around a groove | **Select Chain** |

## The basic workflow

1. Select an example in the model.
2. Open the context menu and start the command you need.
3. Check the magenta highlight.
4. Refine the examples or adjust the range.
5. Click **OK** to confirm, or **Cancel** to restore your original selection.

After OK, the result becomes ordinary Fusion selection. Continue with the native modeling tools.

## Select Similar

### Choose examples

Start with an edge or face you want to match. Use one entity type in each set of examples: edges or faces.

Selectra proposes the closest group. Depending on the task, it considers shape, dimensions, geometry type, and position relative to the examples.

**Separate planar faces** can describe different shape and size families. For example, a small and a large shaped face can select matching elements in both sizes.

**Connected faces** can describe an entire repeating group. This is useful for repeating features and groove walls, where both individual shapes and their arrangement matter.

Use **Examples** to add or remove an example in the dialog. Adding an example recalculates the result and resets the automatic range.

### Choose the scope

| Search Scope | Search area |
| --- | --- |
| **This Body** | The source body in the selected instance |
| **This Component** | The first example's component instance and its entire nested hierarchy |
| **All Components** | All visible, selectable bodies in the assembly |

**This Component** is the default. Another instance of the same component is not included just because it shares a definition. It must belong to the selected hierarchy, or you can use **All Components**.

Examples and exclusions must belong to the current scope. Before narrowing the scope, remove examples that would fall outside it.

### Expand or narrow the result

**Similarity** controls the matching range. Expanding adds the next group; narrowing removes the last included group. Your examples remain selected.

Within the same geometric group, the order is:

1. In the example planes.
2. In parallel planes.
3. In other planes.

Empty groups are skipped. Further expansion includes broader matches; use the highlight and the dialog explanation to check the result.

| Action | Keys |
| --- | --- |
| Expand the range | **PgUp** or **=** |
| Narrow the range | **PgDown** or **-** |

The slider and keys control the same range. The mouse wheel continues to navigate the Fusion view.

### Remove unwanted matches

Use **Exclude** to identify an element that should not belong to the result. Selectra recalculates the proposal with that feedback.

For repeating groups, excluding one member can reject the corresponding group as a whole. This keeps matching groups intact.

### Set a criterion explicitly

Under **Refine → Match**, choose an available criterion such as **Area**, **Length**, **Radius**, or **Orientation**. The available choices depend on the selected geometry.

**Automatic** interprets the geometry of your examples. An explicit criterion is useful when you want one specific property, such as an identical radius despite other size differences.

**Reset Range** restores the automatic range.

## Select Chain

### Closed edge loops

Select an edge on the contour and start **Select Chain**. Selectra proposes the nearest closed loop passing through the example.

Several edges can specify which contour you want. Each proposed contour must pass through all selected examples.

### Closed wall chains

Select an inside wall face of a groove or pocket. **Select Chain** collects the surrounding closed wall chain. Inner contours take priority over broader outer paths.

The result consists of faces, so after OK you can continue working with the wall surfaces.

### Continue across bodies

**Chain across contact** is enabled by default. It continues a chain between bodies with complete, exact contact, such as parts created by **Split Body**.

Gaps, partial contact, and overlapping volumes do not create a connection. Matching edge endpoints alone are also insufficient. The original bodies remain separate, and their geometry and timeline stay unchanged.

Turn the option off to restrict chains to the topology of individual bodies.

### Chain range

**Contour**, **PgUp / =**, and **PgDown / -** switch between complete closed contours through all examples. Each choice replaces the previous contour.

If no closed contour passes through the examples, Selectra reports it. Choose another example or refine the starting set.

## Highlight and confirmation

The **magenta highlight** shows the proposed set before it becomes ordinary selection. The last added group receives an additional outline accent.

- **OK** confirms the set and closes the command.
- **Cancel** restores the original selection.

If the model geometry changes, finish the command and start the search again.

[FAQ](FAQ.md) · [Installation](INSTALLATION.md) · [Home](../README.md)
