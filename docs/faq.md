# FAQ


**Failed to get event while the modal operation is running. (e.g. G + X, S + Y, ...)**

Try to enable the experimental option *Get Event Aggressively*.
This option enables you to get events even if the modal operation is running.

This option hacks the internal structure of Blender, so it is now experimental option.
If you want to use this add-on safely, you should not enable this option.
But the bug reports are welcomed.


**Screencast Keys is disabled after opening a new .blend file or restarting Blender.**

Screencast Keys add-on uses the modal operator which continuously runs Blender's background.
The modal operator will be cancelled when a new file is opened or Blender is restarted.
For this reason, Screencast Keys will be disabled after opening a new .blend file or restarting Blender.

Instead, Screencast Keys provides the shortcut key *Shift + Alt + C* to enable Screencast Keys add-on easily.
See also [Tutorial](tutorial.md#shortcut-keys).


**Auto saving feature is disabled when Screencast Keys add-on is enabled.**

Screencast Keys add-on uses the modal operator which continuously runs Blender's background.
If the modal operator is running, Blender will disable the auto saving feature.
For this reason, the auto saving feature is disabled when Screencast Keys add-on is enabled.
