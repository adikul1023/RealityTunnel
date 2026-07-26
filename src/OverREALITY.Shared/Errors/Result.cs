namespace OverREALITY.Shared.Errors;

public class Result<TValue, TError>
{
    public TValue? Value { get; }
    public TError? Error { get; }
    public bool IsSuccess { get; }

    private Result(TValue? value, TError? error, bool isSuccess)
    {
        Value = value;
        Error = error;
        IsSuccess = isSuccess;
    }

    public static Result<TValue, TError> Success(TValue value) => new(value, default, true);
    public static Result<TValue, TError> Failure(TError error) => new(default, error, false);
}
