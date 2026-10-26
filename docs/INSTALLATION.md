# Install Selectra

**English** · [Русский](INSTALLATION.ru.md)

Selectra is an add-in for Autodesk Fusion on Windows and macOS. Fusion must be installed; no separate Python interpreter or additional packages are required.

## Download

1. Open [Selectra Releases](https://github.com/4FusionLab/Selectra/releases).
2. Download the add-in archive from **Assets** for the release you want.
3. Extract it to a permanent folder on your computer.
4. Find the `Selectra` folder containing both `Selectra.py` and `Selectra.manifest`.

Fusion loads the files directly from this folder. Keep it in place after adding the add-in.

## Add it to Fusion

1. Open **Utilities → Scripts and Add-Ins**.
2. Click **+ → Script or add-in from device**.
3. Select the `Selectra` folder containing `Selectra.py` and `Selectra.manifest`.
4. Select Selectra in the add-ins list and click **Run**.
5. Enable **Run on Startup** if you want the add-in to start with Fusion.

Control names refer to the English Fusion interface.

## Start selecting

Open a Design document and select a BRep edge or face. The context menu offers:

- **Select Similar** — find matching elements.
- **Select Chain** — follow closed edge loops and wall chains.

The result appears as a magenta highlight. Click **OK** to apply ordinary Fusion selection, or **Cancel** to restore the original selection.

[Read the user guide →](GUIDE.md)

## Update

1. Finish any open Selectra command.
2. In **Scripts and Add-Ins**, select Selectra and click **Stop**.
3. Extract the new release and replace the add-in files in its permanent folder.
4. Return to Fusion and click **Run**.

If you move the add-in to another folder, remove the old entry and add the new folder through **+ → Script or add-in from device**.

## Uninstall

1. Finish any open Selectra command.
2. Click **Stop** and turn off **Run on Startup**, if enabled.
3. Remove the Selectra entry from **Scripts and Add-Ins**.
4. Delete the add-in folder if you no longer need it.

## If the commands do not appear

Check that Selectra is running, a Design document is open, and your selection contains BRep edges or faces of one type. Finish any other active Fusion command and open the context menu again.

If the add-in does not start, check that you selected the inner `Selectra` folder rather than the root of the extracted repository. It must contain both `Selectra.py` and `Selectra.manifest`.

[More questions](FAQ.md) · [Report a problem](https://github.com/4FusionLab/Selectra/issues/new/choose) · [Home](../README.md)
