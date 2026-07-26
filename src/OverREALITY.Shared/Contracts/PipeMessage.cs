namespace OverREALITY.Shared.Contracts;

public class PipeMessage<T>
{
    public int Version { get; set; } = 1;
    public string Type { get; set; } = typeof(T).Name;
    public T? Payload { get; set; }
}
