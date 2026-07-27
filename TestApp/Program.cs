using System;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;

class Program
{
    static async Task Main()
    {
        var httpClient = new HttpClient();
        var accessToken = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlZDA5ODQ5NS02ZmMxLTQ3OTItYWI1NC1jOTZjZDNmNmIwOTMiLCJhY2NvdW50IjoiU1QtVFBBNC1WUVRZIiwiZGV2aWNlIjoiM2JlYWI1NzgtNzYzNi00NGU3LTkwZTktYjY2MDBjMzMyMGJhIiwiaXNzIjoiUmVhbGl0eVR1bm5lbCBCaWxsaW5nL0F1dGgiLCJhdWQiOiJSZWFsaXR5VHVubmVsIENsaWVudCIsImlhdCI6MTc4NTA1NzEzMSwibmJmIjoxNzg1MDU3MTMxLCJleHAiOjE3ODUwNTgwMzEsImp0aSI6IjBkOTU4NzE0NTdmZDUwMWFlNjA4ZjYwYTRkM2ExNDQ2In0.5mqHdV3ND2p9CgbpkJr-bquQMKPA8ngwksCEMKd7BsZKmugFa5Ks1NH8VGTnBjqkbR3w4Wdq0nflkHuFRhudDQ";
        
        // 1. Delete tempGuid
        var deleteRequest = new HttpRequestMessage(HttpMethod.Delete, "https://api.stealthy.co.in/api/devices/3beab578-7636-44e7-90e9-b6600c3320ba");
        deleteRequest.Headers.Add("Authorization", "Bearer " + accessToken);
        var deleteResponse = await httpClient.SendAsync(deleteRequest);
        Console.WriteLine("Delete Temp Guid: " + await deleteResponse.Content.ReadAsStringAsync());

        // 2. Reactivate user's device
        var reactivateRequest = new HttpRequestMessage(HttpMethod.Post, "https://api.stealthy.co.in/api/devices/9a94933b-0a90-48da-b803-b10d76eeea9a/reactivate");
        reactivateRequest.Headers.Add("Authorization", "Bearer " + accessToken);
        var reactivateResponse = await httpClient.SendAsync(reactivateRequest);
        Console.WriteLine("Reactivate User Guid: " + await reactivateResponse.Content.ReadAsStringAsync());
    }
}
