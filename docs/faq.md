# FAQ

### Failed to install this add-on

Try to restart Blender or reinstall this add-on.  
Related error is reported in some issues ([Issue #61](https://github.com/nutti/Screencast-Keys/issues/61), [Issue #64](https://github.com/nutti/Screencast-Keys/issues/64), [Issues #65](https://github.com/nutti/Screencast-Keys/issues/65)).

---

### Failed to get event while the modal operation is running. (e.g. G + X, S + Y, ...)

Try to enable the experimental option *Get Event Aggressively*.  
This option enables you to get events even if the modal operation is running.

This option hacks the internal structure of Blender, so it is now experimental option.  
If you want to use this add-on safely, you should not enable this option.  
But the bug reports are welcomed.

---

### Screencast Keys is disabled after opening a new .blend file or restarting Blender.

Use Screencast Keys whose version is above 3.6.  
This issue is solved by [**@CheeryLee**](https://github.com/CheeryLee)'s [Pull Request #62](https://github.com/nutti/Screencast-Keys/pull/62) and his patch is available since v3.6.

---

### Auto saving feature is disabled when Screencast Keys add-on is enabled.

Screencast Keys add-on uses the modal operator which continuously runs Blender's background.  
If the modal operator is running, Blender will disable the auto saving feature.  
For this reason, the auto saving feature is disabled when Screencast Keys add-on is enabled.

---

### ERROR: `TypeError: an integer is required (got type _PropertyDefered)`.

Use Screencast Keys whose version is above 3.5.  
This issue firstly reported in the [Issue #45](https://github.com/nutti/Screencast-Keys/issues/45), and you can find the discussion in it.
