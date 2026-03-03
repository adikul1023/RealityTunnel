using System;
using System.Runtime.InteropServices;

namespace RealityTunnel;

/// <summary>
/// System-tray icon via pure Win32 P/Invoke. No WinForms or extra NuGet required.
/// </summary>
public class TrayIcon : IDisposable
{
    // ── Win32 imports ──────────────────────────────────────────────────────
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern bool Shell_NotifyIcon(uint dwMessage, ref NOTIFYICONDATA pnid);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern ushort RegisterClassEx(ref WNDCLASSEX lpwcx);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateWindowEx(uint ex, string cls, string name, uint style,
        int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr param);

    [DllImport("user32.dll")]
    private static extern bool DestroyWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern IntPtr DefWindowProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern IntPtr CreateIcon(IntPtr hInst, int w, int h,
        byte planes, byte bpp, byte[] and, byte[] xor);

    [DllImport("user32.dll")]
    private static extern bool DestroyIcon(IntPtr hIcon);

    [DllImport("user32.dll")]
    private static extern IntPtr CreatePopupMenu();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern bool AppendMenu(IntPtr hMenu, uint flags, uint id, string text);

    [DllImport("user32.dll")]
    private static extern bool DestroyMenu(IntPtr hMenu);

    [DllImport("user32.dll")]
    private static extern uint TrackPopupMenuEx(IntPtr menu, uint flags, int x, int y, IntPtr hWnd, IntPtr tpm);

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT pt);

    [DllImport("user32.dll")]
    private static extern bool SetForegroundWindow(IntPtr hWnd);

    // ── Structs ───────────────────────────────────────────────────────────
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NOTIFYICONDATA
    {
        public uint   cbSize;
        public IntPtr hWnd;
        public uint   uID;
        public uint   uFlags;
        public uint   uCallbackMessage;
        public IntPtr hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string szTip;
        public uint   dwState, dwStateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string szInfo;
        public uint   uTimeout;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]  public string szInfoTitle;
        public uint   dwInfoFlags;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WNDCLASSEX
    {
        public uint     cbSize, style;
        public WndProc  lpfnWndProc;
        public int      cbClsExtra, cbWndExtra;
        public IntPtr   hInstance, hIcon, hCursor, hbrBackground;
        public string   lpszMenuName, lpszClassName;
        public IntPtr   hIconSm;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int X, Y; }

    private delegate IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    // ── Constants ─────────────────────────────────────────────────────────
    private const uint NIM_ADD    = 0, NIM_MODIFY = 1, NIM_DELETE = 2;
    private const uint NIF_MSG    = 1, NIF_ICON = 2, NIF_TIP = 4, NIF_INFO = 16;
    private const uint NIIF_INFO  = 1;
    private const uint WM_APP_TRAY = 0x8001;
    private const int  WM_RBUTTONUP = 0x0205, WM_LBUTTONDBLCLK = 0x0203;
    private const uint MF_STRING  = 0;
    private const uint TPM_RIGHT  = 0x0002, TPM_RETURNCMD = 0x0100;
    private const uint CMD_SHOW = 1, CMD_DISCONNECT = 2, CMD_EXIT = 3;
    private const string CLASS = "OverREALITY_Tray";

    // ── Fields ────────────────────────────────────────────────────────────
    private readonly MainWindow _window;
    private readonly WndProc    _proc; // pinned delegate
    private IntPtr _hwnd, _hGray, _hGreen;
    private NOTIFYICONDATA _nid;
    private bool _disposed;

    public TrayIcon(MainWindow window)
    {
        _window = window;
        _proc   = WndProcCb; // keep delegate alive

        _hGray  = MakeCircleIcon(110, 110, 110);
        _hGreen = MakeCircleIcon(50,  205, 100);

        var wcx = new WNDCLASSEX
        {
            cbSize       = (uint)Marshal.SizeOf<WNDCLASSEX>(),
            lpfnWndProc  = _proc,
            lpszClassName = CLASS,
            hInstance    = Marshal.GetHINSTANCE(typeof(TrayIcon).Module)
        };
        RegisterClassEx(ref wcx);

        // HWND_MESSAGE = -3 — message-only window, never shown
        _hwnd = CreateWindowEx(0, CLASS, "", 0, 0, 0, 0, 0,
            new IntPtr(-3), IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);

        _nid = new NOTIFYICONDATA
        {
            cbSize           = (uint)Marshal.SizeOf<NOTIFYICONDATA>(),
            hWnd             = _hwnd,
            uID              = 1,
            uFlags           = NIF_MSG | NIF_ICON | NIF_TIP,
            uCallbackMessage = WM_APP_TRAY,
            hIcon            = _hGray,
            szTip            = "OverREALITY — Disconnected"
        };
        Shell_NotifyIcon(NIM_ADD, ref _nid);
    }

    public void SetConnected(bool connected)
    {
        _nid.hIcon  = connected ? _hGreen : _hGray;
        _nid.szTip  = connected ? "OverREALITY — Connected" : "OverREALITY — Disconnected";
        _nid.uFlags = NIF_ICON | NIF_TIP;
        Shell_NotifyIcon(NIM_MODIFY, ref _nid);
    }

    public void ShowBalloon(string message)
    {
        _nid.uFlags     = NIF_INFO;
        _nid.szInfo     = message;
        _nid.szInfoTitle = "OverREALITY";
        _nid.dwInfoFlags = NIIF_INFO;
        _nid.uTimeout   = 2000;
        Shell_NotifyIcon(NIM_MODIFY, ref _nid);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _nid.uFlags = 0;
        Shell_NotifyIcon(NIM_DELETE, ref _nid);
        if (_hwnd  != IntPtr.Zero) { DestroyWindow(_hwnd);  _hwnd  = IntPtr.Zero; }
        if (_hGray  != IntPtr.Zero) { DestroyIcon(_hGray);  _hGray  = IntPtr.Zero; }
        if (_hGreen != IntPtr.Zero) { DestroyIcon(_hGreen); _hGreen = IntPtr.Zero; }
    }

    // ── WndProc ───────────────────────────────────────────────────────────
    private IntPtr WndProcCb(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam)
    {
        if (msg == WM_APP_TRAY)
        {
            int ev = (int)(lParam.ToInt64() & 0xFFFF);
            if (ev == WM_LBUTTONDBLCLK)
                _window.DispatcherQueue.TryEnqueue(_window.ShowFromTray);
            else if (ev == WM_RBUTTONUP)
                ShowContextMenu();
        }
        return DefWindowProc(hWnd, msg, wParam, lParam);
    }

    private void ShowContextMenu()
    {
        GetCursorPos(out var pt);
        SetForegroundWindow(_hwnd);
        var menu = CreatePopupMenu();
        AppendMenu(menu, MF_STRING, CMD_SHOW,       "Show");
        AppendMenu(menu, MF_STRING, CMD_DISCONNECT, "Disconnect");
        AppendMenu(menu, MF_STRING, CMD_EXIT,       "Exit");
        uint cmd = TrackPopupMenuEx(menu, TPM_RIGHT | TPM_RETURNCMD, pt.X, pt.Y, _hwnd, IntPtr.Zero);
        DestroyMenu(menu);
        switch (cmd)
        {
            case CMD_SHOW:       _window.DispatcherQueue.TryEnqueue(_window.ShowFromTray);      break;
            case CMD_DISCONNECT: _window.DispatcherQueue.TryEnqueue(_window.DisconnectFromTray); break;
            case CMD_EXIT:       _window.DispatcherQueue.TryEnqueue(_window.ExitApp);           break;
        }
    }

    // ── Icon builder ──────────────────────────────────────────────────────
    private static IntPtr MakeCircleIcon(byte r, byte g, byte b)
    {
        const int S = 16;
        var xor = new byte[S * S * 4]; // 32bpp BGRA
        var and = new byte[S * S / 8]; // AND mask — all 0 = fully opaque in XOR region

        float cx = (S - 1) / 2f, cy = (S - 1) / 2f, rad = S / 2f - 1f;
        for (int y = 0; y < S; y++)
        for (int x = 0; x < S; x++)
        {
            float dx = x - cx, dy = y - cy;
            if (dx * dx + dy * dy <= rad * rad)
            {
                int i = (y * S + x) * 4;
                xor[i] = b; xor[i+1] = g; xor[i+2] = r; xor[i+3] = 255;
            }
        }
        return CreateIcon(IntPtr.Zero, S, S, 1, 32, and, xor);
    }
}
