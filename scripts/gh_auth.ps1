# Reads the stored GitHub credential and exposes it as $env:GH_TOKEN.
# Dot-source this before using gh:  . scripts\gh_auth.ps1
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class CredUtil {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL {
        public int Flags; public int Type; public IntPtr TargetName; public IntPtr Comment;
        public long LastWritten; public int CredentialBlobSize; public IntPtr CredentialBlob;
        public IntPtr TargetAlias; public IntPtr UserName;
    }
    [DllImport("Advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, int type, int flag, out IntPtr credential);
    [DllImport("Advapi32.dll", EntryPoint = "CredFree", SetLastError = true)]
    private static extern void CredFree(IntPtr buffer);
    public static string Read(string target) {
        IntPtr ptr;
        if (!CredRead(target, 1, 0, out ptr)) return null;
        try {
            CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(ptr, typeof(CREDENTIAL));
            if (cred.CredentialBlob == IntPtr.Zero || cred.CredentialBlobSize <= 0) return null;
            return Marshal.PtrToStringUni(cred.CredentialBlob, cred.CredentialBlobSize / 2);
        } finally { CredFree(ptr); }
    }
}
"@
$env:GH_TOKEN = [CredUtil]::Read("git:https://github.com")
