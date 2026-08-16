using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

class Launcher
{
    static void Main()
    {
        string projectDir = @"c:\Users\avaka\OneDrive\Desktop\Powerpoint";
        string batPath = Path.Combine(projectDir, "run_app.bat");

        if (!File.Exists(batPath))
        {
            MessageBox.Show(
                "Proje klasoru tasinmis veya silinmis olabilir:\n" + batPath,
                "Limon Arisi Sunum Otomasyonu",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return;
        }

        var psi = new ProcessStartInfo
        {
            FileName = batPath,
            WorkingDirectory = projectDir,
            UseShellExecute = true,
            WindowStyle = ProcessWindowStyle.Normal
        };
        Process.Start(psi);
    }
}
