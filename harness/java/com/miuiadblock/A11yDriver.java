package com.miuiadblock;

import android.os.Bundle;
import android.view.accessibility.AccessibilityNodeInfo;

import com.android.uiautomator.testrunner.UiAutomatorTestCase;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

/**
 * Accessibility driver for MIUI's Settings UI.
 *
 * <p>MIUI 12 blocks {@code InputManager.injectInputEvent()} for the adb/shell identity,
 * but it does not block accessibility actions. This driver runs inside the stock
 * {@code uiautomator runtest} harness and therefore performs clicks, scrolls and text
 * entry through the accessibility service instead of the raw input pipeline.
 *
 * <p>Protocol: the harness reads one command per line from
 * {@code /data/local/tmp/miui_a11y_cmd.txt}:
 *
 * <pre>
 *   click &lt;text&gt;       find a node with an exact text, scroll to it, click it
 *   clickcontains &lt;text&gt; same, but substring match
 *   clickid &lt;res-id&gt;    click the first node with the given resource-id
 *   detail &lt;text&gt;      click the "⋮" (preference_detail) button of the row with that text
 *   long &lt;text&gt;        long-click a node with an exact text
 *   text &lt;value&gt;       type text into the focused editable field
 *   dump                  print the accessibility tree of the active window
 * </pre>
 *
 * <p>Every command prints exactly one result line prefixed with {@code [miui-a11y]},
 * so the caller can parse the outcome without scraping free-form logs.
 */
public class A11yDriver extends UiAutomatorTestCase {

    private static final String CMD_FILE = "/data/local/tmp/miui_a11y_cmd.txt";
    private static final String PREFIX = "[miui-a11y]";

    private Object bridge;
    private Method getRoot;

    @Override
    public void setUp() throws Exception {
        super.setUp();
        Object device = getClass().getMethod("getUiDevice").invoke(this);
        Field field = device.getClass().getDeclaredField("mUiAutomationBridge");
        field.setAccessible(true);
        bridge = field.get(device);
        getRoot = bridge.getClass().getMethod("getRootInActiveWindow");
        limitIdleWait();
    }

    public void testDriver() throws Exception {
        String[] args = readCommand();
        if (args.length == 0) {
            result("ERR empty command");
            return;
        }
        String verb = args[0];
        String argument = args.length > 1 ? args[1] : "";

        switch (verb) {
            case "click":
                runClick(argument, true);
                break;
            case "clickcontains":
                runClick(argument, false);
                break;
            case "clickid":
                runClickById(argument);
                break;
            case "detail":
                runDetail(argument);
                break;
            case "long":
                runLong(argument);
                break;
            case "text":
                runText(argument);
                break;
            case "dump":
                runDump();
                break;
            default:
                result("ERR unknown verb " + verb);
        }
    }

    /* ---------------------------------------------------------------- commands */

    private void runClick(String text, boolean exact) {
        AccessibilityNodeInfo node = findWithScroll(text, exact);
        if (node == null) {
            result("ERR not-found " + text);
            return;
        }
        AccessibilityNodeInfo clickable = node;
        if (!clickable.isClickable()) {
            clickable = firstClickableAncestor(node);
        }
        if (clickable == null) {
            result("ERR not-clickable " + text);
            return;
        }
        boolean ok = clickable.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        result((ok ? "OK click " : "ERR click-failed ") + text);
    }

    private void runClickById(String resourceId) {
        AccessibilityNodeInfo node = findByResourceId(root(), resourceId);
        if (node == null) {
            result("ERR id-not-found " + resourceId);
            return;
        }
        boolean ok = node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        result((ok ? "OK clickid " : "ERR clickid-failed ") + resourceId);
    }

    /** Clicks the "⋮" (preference_detail) button that belongs to the row titled {@code text}. */
    private void runDetail(String text) {
        AccessibilityNodeInfo title = findWithScroll(text, true);
        if (title == null) {
            result("ERR not-found " + text);
            return;
        }
        AccessibilityNodeInfo row = title.getParent();
        int depth = 0;
        while (row != null && !row.isClickable() && depth < 6) {
            row = row.getParent();
            depth++;
        }
        AccessibilityNodeInfo button = findByResourceId(row, "preference_detail");
        if (button == null) {
            result("ERR detail-not-found " + text);
            return;
        }
        boolean ok = button.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        result((ok ? "OK detail " : "ERR detail-failed ") + text);
    }

    private void runLong(String text) {
        AccessibilityNodeInfo node = findWithScroll(text, true);
        if (node == null) {
            result("ERR not-found " + text);
            return;
        }
        boolean ok = node.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK);
        result((ok ? "OK long " : "ERR long-failed ") + text);
    }

    private void runText(String value) {
        AccessibilityNodeInfo field = findByClass(root(), "android.widget.EditText");
        if (field == null) {
            result("ERR no-edit-field");
            return;
        }
        try {
            android.os.Bundle args = new android.os.Bundle();
            args.putCharSequence(
                    AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, value);
            boolean ok = field.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
            result((ok ? "OK text " : "ERR text-failed ") + value.length() + "chars");
        } catch (Throwable t) {
            result("ERR text-failed " + t);
        }
    }

    private void runDump() {
        AccessibilityNodeInfo root = root();
        if (root == null) {
            result("ERR no-root");
            return;
        }
        dump(root, 0);
        result("OK dump");
    }

    /* ------------------------------------------------------------- tree search */

    /** Finds a node by text, scrolling the active list until it shows up. */
    private AccessibilityNodeInfo findWithScroll(String text, boolean exact) {
        AccessibilityNodeInfo node = findByText(root(), text, exact);
        if (node != null) {
            return node;
        }
        for (int attempt = 0; attempt < 15; attempt++) {
            // Scroll on a *fresh* node: nodes obtained from the window enumeration go
            // stale after the list moved, and actions on them are silently rejected.
            AccessibilityNodeInfo fresh = freshRoot();
            AccessibilityNodeInfo scrollable = findScrollable(fresh);
            if (scrollable == null) {
                trace("no-scrollable-node");
                return null;
            }
            boolean scrolled = scrollable.performAction(AccessibilityNodeInfo.ACTION_SCROLL_FORWARD);
            trace("scroll " + (attempt + 1) + " -> " + scrolled);
            if (!scrolled) {
                return null;
            }
            sleep(600);
            node = findByText(root(), text, exact);
            if (node != null) {
                return node;
            }
        }
        return null;
    }

    /**
     * Scrolls the active list until an element whose text contains {@code text} is visible.
     *
     * <p>Uses the classic {@code com.android.uiautomator.core.UiScrollable} shipped on the
     * device; it is invoked reflectively because the host SDK cannot compile against the
     * device-side dex jar.
     */
    private boolean scrollIntoView(String text) {
        try {
            Class<?> selectorClass = Class.forName("com.android.uiautomator.core.UiSelector");
            Object selector = selectorClass.getConstructor().newInstance();
            selectorClass.getMethod("scrollable", boolean.class).invoke(selector, true);
            selectorClass.getMethod("textContains", String.class).invoke(selector, text);

            Class<?> scrollableClass = Class.forName("com.android.uiautomator.core.UiScrollable");
            Object scrollable = scrollableClass.getConstructor(selectorClass).newInstance(selector);
            Method intoView = scrollableClass.getMethod("scrollIntoView", selectorClass);
            return Boolean.TRUE.equals(intoView.invoke(scrollable, selector));
        } catch (Throwable t) {
            trace("scroll-into-view exception " + t);
            return false;
        }
    }

    private AccessibilityNodeInfo findByText(AccessibilityNodeInfo node, String text, boolean exact) {
        if (node == null) {
            return null;
        }
        CharSequence value = node.getText();
        String own = value == null ? "" : value.toString();
        if (exact ? own.equals(text) : own.contains(text)) {
            return node;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findByText(node.getChild(i), text, exact);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findByResourceId(AccessibilityNodeInfo node, String suffix) {
        if (node == null) {
            return null;
        }
        String id = node.getViewIdResourceName();
        if (id != null && (id.equals(suffix) || id.endsWith(suffix))) {
            return node;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findByResourceId(node.getChild(i), suffix);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findByClass(AccessibilityNodeInfo node, String className) {
        if (node == null) {
            return null;
        }
        if (className.equals(node.getClassName())) {
            return node;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findByClass(node.getChild(i), className);
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private AccessibilityNodeInfo findScrollable(AccessibilityNodeInfo node) {
        if (node == null) {
            return null;
        }
        if (node.isScrollable()) {
            return node;
        }
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = findScrollable(node.getChild(i));
            if (found != null) {
                return found;
            }
        }
        return null;
    }

    private AccessibilityNodeInfo firstClickableAncestor(AccessibilityNodeInfo node) {
        AccessibilityNodeInfo current = node.getParent();
        int depth = 0;
        while (current != null && depth < 6) {
            if (current.isClickable()) {
                return current;
            }
            current = current.getParent();
            depth++;
        }
        return null;
    }

    /* ------------------------------------------------------------------ roots */

    /**
     * Active window root.
     *
     * <p>{@code getRootInActiveWindow()} waits for the UI to become idle and therefore
     * returns {@code null} on a screen that never settles (MIUI's Wi-Fi list animates, and
     * a broken digitiser can generate phantom touches). The fallback enumerates the
     * accessibility windows directly and picks the active one.
     */
    /**
     * Shortens the idle wait of {@code getRootInActiveWindow()}.
     *
     * <p>The default timeout is ten seconds, which is longer than the whole harness
     * budget on a screen that never settles (MIUI's Settings list animates, and a
     * broken digitiser can keep generating touches).
     */
    private void limitIdleWait() {
        try {
            Class<?> automationClass = Class.forName("android.app.UiAutomation");
            Field field = bridge.getClass().getSuperclass().getDeclaredField("mUiAutomation");
            field.setAccessible(true);
            Object automation = field.get(bridge);
            Method setter = automationClass.getMethod("setWaitForIdleTimeout", int.class);
            setter.invoke(automation, 1500);
        } catch (Throwable ignored) {
            // keep the default timeout
        }
    }

    /** Root of the active window; may be null when the UI never goes idle. */
    private AccessibilityNodeInfo root() {
        AccessibilityNodeInfo fresh = freshRoot();
        if (fresh != null) {
            return fresh;
        }
        return rootFromWindows();
    }

    /**
     * Root obtained from {@code getRootInActiveWindow()}.
     *
     * <p>Waits for the UI to settle, so it can return null on a permanently animating
     * screen. Nodes from here are always current, which matters for actions.
     */
    private AccessibilityNodeInfo freshRoot() {
        try {
            return (AccessibilityNodeInfo) getRoot.invoke(bridge);
        } catch (Throwable ignored) {
            return null;
        }
    }

    private AccessibilityNodeInfo rootFromWindows() {
        try {
            Class<?> automationClass = Class.forName("android.app.UiAutomation");
            Field field = bridge.getClass().getSuperclass().getDeclaredField("mUiAutomation");
            field.setAccessible(true);
            Object automation = field.get(bridge);
            Method getWindows = automationClass.getMethod("getWindows");
            @SuppressWarnings("unchecked")
            List<Object> windows = (List<Object>) getWindows.invoke(automation);
            AccessibilityNodeInfo fallback = null;
            for (Object window : windows) {
                Class<?> windowClass = window.getClass();
                Method isActive = windowClass.getMethod("isActive");
                Method getWindowRoot = windowClass.getMethod("getRoot");
                AccessibilityNodeInfo node = (AccessibilityNodeInfo) getWindowRoot.invoke(window);
                if (Boolean.TRUE.equals(isActive.invoke(window)) && node != null) {
                    return node;
                }
                if (node != null && fallback == null) {
                    fallback = node;
                }
            }
            return fallback;
        } catch (Throwable ignored) {
            return null;
        }
    }

    /* ------------------------------------------------------------------ misc */

    /** {@code getBoundsInScreen()} changed signature in API 30; the Rect form works on API 28. */
    private static String boundsOf(AccessibilityNodeInfo node) {
        try {
            android.graphics.Rect rect = new android.graphics.Rect();
            node.getBoundsInScreen(rect);
            return rect.toString();
        } catch (Throwable t) {
            return "?";
        }
    }

    private void dump(AccessibilityNodeInfo node, int depth) {
        if (node == null) {
            return;
        }
        StringBuilder line = new StringBuilder();
        for (int i = 0; i < depth; i++) {
            line.append("  ");
        }
        line.append(node.getClassName())
            .append(" id=").append(node.getViewIdResourceName())
            .append(" text=").append(node.getText())
            .append(" desc=").append(node.getContentDescription())
            .append(" clickable=").append(node.isClickable())
            .append(" checked=").append(node.isChecked())
            .append(" scrollable=").append(node.isScrollable())
            .append(" bounds=").append(boundsOf(node));
        System.out.println(line.toString());
        for (int i = 0; i < node.getChildCount(); i++) {
            dump(node.getChild(i), depth + 1);
        }
    }

    private String[] readCommand() {
        try {
            java.io.File file = new java.io.File(CMD_FILE);
            if (!file.exists()) {
                return new String[0];
            }
            byte[] buffer = new byte[(int) file.length()];
            java.io.FileInputStream in = new java.io.FileInputStream(file);
            int read = in.read(buffer);
            in.close();
            String line = new String(buffer, 0, Math.max(read, 0), "UTF-8").trim();
            if (line.isEmpty()) {
                return new String[0];
            }
            int space = line.indexOf(' ');
            if (space < 0) {
                return new String[] { line };
            }
            return new String[] { line.substring(0, space), line.substring(space + 1) };
        } catch (Throwable t) {
            return new String[0];
        }
    }

    /** Trace line: printed before the final result, ignored by the caller. */
    private void trace(String message) {
        System.out.println(PREFIX + " TRACE " + message);
        System.out.flush();
    }

    private void result(String message) {
        System.out.println(PREFIX + " " + message);
        System.out.flush();
    }

    private void sleep(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
    }
}
