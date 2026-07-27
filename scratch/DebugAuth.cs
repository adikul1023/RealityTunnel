using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Text.Json;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new HttpClient();
        client.BaseAddress = new Uri("https://api.stealthy.co.in");

        var payload = new {
            account_id = "ST-TEST-1234",
            master_token = "abcdef123456abcdef123456abcdef123456abcdef123456abcdef123456abcd",
            device_guid = Environment.MachineName
        };

        var requestJson = JsonSerializer.Serialize(payload);
        Console.WriteLine("AUTH REQUEST: URL=/api/auth/login Payload=" + requestJson);

        var response = await client.PostAsJsonAsync("/api/auth/login", payload);
        var responseContent = await response.Content.ReadAsStringAsync();
        
        Console.WriteLine($"AUTH RESPONSE: Status={(int)response.StatusCode} Body={responseContent}");
    }
}
