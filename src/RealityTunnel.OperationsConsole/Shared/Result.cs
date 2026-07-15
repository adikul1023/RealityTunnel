using System;

namespace RealityTunnel.OperationsConsole.Shared
{
    public class ApiResult<T>
    {
        public bool IsSuccess { get; }
        public T? Data { get; }
        public string? ErrorMessage { get; }
        public int StatusCode { get; }
        public bool IsUnauthorized { get; }
        public bool IsForbidden { get; }

        private ApiResult(bool isSuccess, T? data, string? errorMessage, int statusCode, bool isUnauthorized = false, bool isForbidden = false)
        {
            IsSuccess = isSuccess;
            Data = data;
            ErrorMessage = errorMessage;
            StatusCode = statusCode;
            IsUnauthorized = isUnauthorized;
            IsForbidden = isForbidden;
        }

        public static ApiResult<T> Success(T data, int statusCode = 200) => new(true, data, null, statusCode);
        public static ApiResult<T> Failure(string errorMessage, int statusCode = 500, bool isUnauthorized = false, bool isForbidden = false) =>
            new(false, default, errorMessage, statusCode, isUnauthorized, isForbidden);
    }
}
