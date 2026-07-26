using OverREALITY.Core.Services;
using OverREALITY.Shared.Api.Configuration;
using Xunit;

namespace OverREALITY.Tests.Core;

public class ServerProfileValidatorTests
{
    private readonly ServerProfileValidator _validator;

    public ServerProfileValidatorTests()
    {
        _validator = new ServerProfileValidator();
    }

    [Fact]
    public void Validate_ValidProfile_ReturnsSuccess()
    {
        var profile = new ServerProfileDto
        {
            Server = "api.stealthy.co.in",
            Port = 443,
            Uuid = "some-uuid",
            Transport = "vless"
        };

        var result = _validator.Validate(profile);

        Assert.True(result.IsSuccess);
    }

    [Fact]
    public void Validate_MissingServer_ReturnsFailure()
    {
        var profile = new ServerProfileDto
        {
            Port = 443,
            Uuid = "some-uuid",
            Transport = "vless"
        };

        var result = _validator.Validate(profile);

        Assert.False(result.IsSuccess);
        Assert.Equal("INVALID_SERVER", result.Error?.Code);
    }

    [Fact]
    public void Validate_InvalidPort_ReturnsFailure()
    {
        var profile = new ServerProfileDto
        {
            Server = "api.stealthy.co.in",
            Port = 0,
            Uuid = "some-uuid",
            Transport = "vless"
        };

        var result = _validator.Validate(profile);

        Assert.False(result.IsSuccess);
        Assert.Equal("INVALID_PORT", result.Error?.Code);
    }
}
