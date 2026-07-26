using OverREALITY.Configuration.Models;

namespace OverREALITY.Configuration;

public interface ISingboxTemplateProvider
{
    SingboxConfig GetBaseTemplate();
}
