// -*- mode: js; js-indent-level: 4; indent-tabs-mode: nil -*-
//
// NetBSD/pkgsrc compatibility overlay for GNOME Shell 40.2.
//
// Current pkgsrc can combine GNOME Shell 40.2 with substantially newer GJS/
// GLib/introspection components.  On this combination Shell.App.app_info can
// occasionally be undefined while GNOME Shell is building the favorites list.
// Upstream GNOME Shell 40.2 assumes a non-null Gio.DesktopAppInfo and crashes
// in shouldShowApp() before the desktop finishes starting.
//
// This file is based on GNOME Shell 40.2 parentalControlsManager.js.  The only
// compatibility change is the explicit null/undefined guard in shouldShowApp().

/* exported getDefault */

const { Gio, GObject, Shell } = imports.gi;

// We require libmalcontent ≥ 0.6.0
const HAVE_MALCONTENT = imports.package.checkSymbol(
    'Malcontent', '0', 'ManagerGetValueFlags');

var Malcontent = null;
if (HAVE_MALCONTENT) {
    Malcontent = imports.gi.Malcontent;
    Gio._promisify(Malcontent.Manager.prototype, 'get_app_filter_async', 'get_app_filter_finish');
}

let _singleton = null;

function getDefault() {
    if (_singleton === null)
        _singleton = new ParentalControlsManager();

    return _singleton;
}

var ParentalControlsManager = GObject.registerClass({
    Signals: {
        'app-filter-changed': {},
    },
}, class ParentalControlsManager extends GObject.Object {
    _init() {
        super._init();

        this._initialized = false;
        this._disabled = false;
        this._appFilter = null;

        this._initializeManager();
    }

    async _initializeManager() {
        if (!HAVE_MALCONTENT) {
            log('Skipping parental controls support as it’s disabled');
            this._initialized = true;
            this.emit('app-filter-changed');
            return;
        }

        log(`Getting parental controls for user ${Shell.util_get_uid()}`);
        try {
            const connection = await Gio.DBus.get(Gio.BusType.SYSTEM, null);
            this._manager = new Malcontent.Manager({ connection });
            this._appFilter = await this._manager.get_app_filter_async(
                Shell.util_get_uid(),
                Malcontent.ManagerGetValueFlags.NONE,
                null);
        } catch (e) {
            if (e.matches(Malcontent.ManagerError, Malcontent.ManagerError.DISABLED)) {
                log('Parental controls globally disabled');
                this._disabled = true;
            } else {
                logError(e, 'Failed to get parental controls settings');
                return;
            }
        }

        this._manager.connect('app-filter-changed', this._onAppFilterChanged.bind(this));

        this._initialized = true;
        this.emit('app-filter-changed');
    }

    async _onAppFilterChanged(manager, uid) {
        let currentUid = Shell.util_get_uid();
        if (currentUid !== uid)
            return;

        try {
            this._appFilter = await this._manager.get_app_filter_async(
                currentUid,
                Malcontent.ManagerGetValueFlags.NONE,
                null);
            this.emit('app-filter-changed');
        } catch (e) {
            logError(e, `Failed to get new MctAppFilter for uid ${Shell.util_get_uid()} on app-filter-changed`);
        }
    }

    get initialized() {
        return this._initialized;
    }

    shouldShowApp(appInfo) {
        // NetBSD/pkgsrc compatibility: do not crash if an old Shell.App object
        // does not expose app_info through the newer GJS/introspection stack.
        // Filtering the unusable entry is preferable to aborting GNOME Shell.
        if (appInfo === null || appInfo === undefined)
            return false;

        if (!appInfo.should_show())
            return false;

        if (!HAVE_MALCONTENT || this._disabled)
            return true;

        if (!this.initialized) {
            log(`Warning: Hiding app because parental controls not yet initialised: ${appInfo.get_id()}`);
            return false;
        }

        return this._appFilter.is_appinfo_allowed(appInfo);
    }
});
