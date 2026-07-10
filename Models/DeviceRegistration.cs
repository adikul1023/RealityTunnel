using System;

namespace RealityTunnel.Models;

public record DeviceRegistration(
    string DeviceGuid,
    string DeviceName,
    string Platform,
    string AppVersion,
    string OsVersion
);
