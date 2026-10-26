# Frequently asked questions

**English** · [Русский](FAQ.ru.md)

## What is the difference between Select Similar and Select Chain?

**Select Similar** finds matching geometry from examples. **Select Chain** follows a closed contour: an edge loop or a chain of wall faces.

## What can I select?

BRep edges and faces, including geometry in components and assemblies. Each set of examples contains either edges or faces.

Sketch entities, mesh bodies, and T-Spline geometry are outside these commands. Imported models are supported when their geometry is represented as BRep bodies.

## Does This Component include nested components?

Yes. It includes the selected component instance and its nested hierarchy. A neighboring instance of the same definition is not added automatically. Use **All Components** to search the entire visible assembly.

## Why are some elements missing from the first set?

The first set contains the closest proposed group. Expand the range with **PgUp**, **=**, or the slider.

Select Similar separates position into levels: the example planes first, parallel planes next, then other planes. Select Chain switches between complete contours through all examples.

## What if the result includes unwanted elements?

In **Select Similar**, add a more representative example to **Examples**, or identify an unwanted element in **Exclude**. For a specific task, choose an explicit criterion under **Refine → Match**.

In **Select Chain**, refine the starting edges or faces that the contour must pass through, or choose another **Contour**.

## Does an identical radius mean an identical feature?

No. Radius is one geometric property. An internal cylinder and an external shaft can have the same radius. With explicit **Match → Radius**, the selection can contain elements serving different purposes.

Check the highlighted proposal before clicking OK.

## Can a chain cross several bodies?

Yes, with **Chain across contact** enabled, when the bodies have complete, exact contact. This includes parts created by **Split Body**.

Gaps, partial contact, point or edge contact alone, and overlapping volumes do not create a connection. With the option off, chains are restricted to the topology of individual bodies.

## Does Selectra merge bodies or create geometry?

No. Its result is a selection of original edges and faces. Model geometry and the timeline stay unchanged.

## Why is the command missing from the context menu?

Check that the add-in is running, a Design document is open, and BRep edges or faces of one type are selected. Finish any other active Fusion command and open the menu again.

[Installation instructions](INSTALLATION.md)

## Do I need to install Python?

No. Selectra uses the Python runtime supplied with Fusion. A separate interpreter and package installation are not required.

## Where does the search run?

Inside Fusion on your computer. Selectra does not send your model to external services to search for matching geometry.

## Why do I need to restart after changing the model?

The result refers to the geometry read when the command started. After changing a body or moving a component, finish the current search and start it again.

## How do I report a problem?

Open an [issue](https://github.com/4FusionLab/Selectra/issues/new/choose). Include the Selectra and Fusion versions, operating system, command, examples, expected result, and actual result.

A screenshot helps explain the selection. A minimal model or steps to create it help reproduce the problem. Share only material you are allowed to publish. Use the [private channel](../SECURITY.md) for vulnerability reports.

[User guide](GUIDE.md) · [Installation](INSTALLATION.md) · [Home](../README.md)
