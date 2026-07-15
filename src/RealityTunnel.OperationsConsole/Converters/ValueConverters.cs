using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace RealityTunnel.OperationsConsole.Converters
{
    public class StatusColorConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            string status = (value?.ToString() ?? string.Empty).ToLowerInvariant();
            return status switch
            {
                "active" or "ok" or "running" or "synced" => new SolidColorBrush(Color.FromRgb(16, 185, 129)),  // Green #10B981
                "suspended" or "error" or "failed" or "terminated" => new SolidColorBrush(Color.FromRgb(239, 68, 68)), // Red #EF4444
                "expired" or "degraded" or "pending" or "warn" => new SolidColorBrush(Color.FromRgb(245, 158, 11)), // Amber #F59E0B
                _ => new SolidColorBrush(Color.FromRgb(107, 114, 128)) // Gray #6B7280
            };
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
            throw new NotImplementedException();
    }

    public class InverseBooleanConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
            value is bool b ? !b : value;

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
            value is bool b ? !b : value;
    }

    public class BooleanToVisibilityConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            bool bVal = value is bool b && b;
            if (Invert) bVal = !bVal;
            return bVal ? Visibility.Visible : Visibility.Collapsed;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
            throw new NotImplementedException();
    }

    public class NullToVisibilityConverter : IValueConverter
    {
        public bool Invert { get; set; } = false;

        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            bool isNull = value is null || (value is string s && string.IsNullOrEmpty(s));
            if (Invert) isNull = !isNull;
            return isNull ? Visibility.Collapsed : Visibility.Visible;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
            throw new NotImplementedException();
    }
}
