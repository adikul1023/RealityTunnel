namespace OverREALITY.Shared.Interfaces;

public interface IDomainResolver
{
    string ApiBaseUrl { get; }
    string EdgeHost { get; }
    string DownloadBase { get; }
}
