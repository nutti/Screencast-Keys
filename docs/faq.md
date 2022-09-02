# FAQ

<!-- markdownlint-disable-next-line MD001 -->
### Failed to install this add-on

On installing the add-on, following errors can be seen in some conditions.

* `ValueError: register_class(...): already registered as a subclass
  'DisplayEventTextAliasProperties'`
  ([Issue #61](https://github.com/nutti/Screencast-Keys/issues/61))
* `AttributeError: module 'screencast_keys.utils' has no attribute
  'addon_updater'`
  ([Issue #64](https://github.com/nutti/Screencast-Keys/issues/64))

If these errors are raised, try to restart/reinstall Blender or reinstall this
add-on.

---

<!-- markdownlint-disable-next-line MD013 -->
### Failed to get event while the modal operation is running (e.g. G + X, S + Y, ...)

Try to enable the experimental option *Get Event Aggressively*.  
This option enables you to get events even if the modal operation is running.

This option hacks the internal structure of Blender, so it is now experimental
option.  
If you want to use this add-on safely, you should not enable this option.  
But the bug reports are welcomed.

---

<!-- markdownlint-disable-next-line MD013 -->
### Screencast Keys is disabled after opening a new .blend file or restarting Blender

Use Screencast Keys whose version is above 3.6.  
This issue is solved by [**@CheeryLee**](https://github.com/CheeryLee)'s
[Pull Request #62](https://github.com/nutti/Screencast-Keys/pull/62) and his
patch is available since v3.6.

---

<!-- markdownlint-disable-next-line MD013 -->
### Auto saving (.blend file) feature is disabled when Screencast Keys add-on is enabled

Screencast Keys add-on uses the modal operator which continuously runs
Blender's background.  
If the modal operator is running, Blender will disable the auto saving
(.blend file) feature.  
For this reason, the auto saving feature is disabled when Screencast Keys
add-on is enabled.

Screencast Keys has a feature to simulate the auto saving against this issue.  
Try to enable the experimental option *Auto Save*.  
This option enables the auto saving while Screencast Keys add-on is enabled.

This option hacks the internal structure of Blender, so it is now experimental
option.  
If you want to use this add-on safely, you should not enable this option.  
But the bug reports are welcomed.

---

### ERROR: `TypeError: an integer is required (got type _PropertyDefered)`

Use Screencast Keys whose version is above 3.5.  
This issue firstly reported in the
[Issue #45](https://github.com/nutti/Screencast-Keys/issues/45), and you can
find the discussion in it.

---

<!-- markdownlint-disable-next-line MD013 -->
### ERROR: `ValueError: bpy_struct "SK_Preferences" registration error: 'font_size' IntProperty could not register (see previous error)`

Use Screencast Keys whose version is above 3.7.
This issue firstly reported in the
[Issue #73](https://github.com/nutti/Screencast-Keys/issues/73), and you can
find the discussion in it.
