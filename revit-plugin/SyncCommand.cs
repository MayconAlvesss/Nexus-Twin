using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Newtonsoft.Json;

namespace NexusTwin.Revit
{
    /// <summary>
    /// Revit External Command to synchronize structural data with the NexusTwin API.
    /// This represents the "BIM Connector" layer mentioned in the roadmap.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    public class SyncCommand : IExternalCommand
    {
        private static readonly HttpClient _client = new HttpClient();
        private const string ApiUrl = "http://localhost:8000/api/v1/elements";
        private const string ApiKey = "nexus-dev-key-change-me";

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            UIDocument uiDoc = commandData.Application.ActiveUIDocument;
            Document doc = uiDoc.Document;

            // 1. Filter structural elements (Columns, Beams)
            FilteredElementCollector collector = new FilteredElementCollector(doc);
            ICollection<Element> structuralElements = collector
                .OfCategory(BuiltInCategory.OST_StructuralColumns)
                .WhereElementIsNotElementType()
                .ToElements();

            try 
            {
                Task.Run(() => SyncWithNexusTwin(structuralElements)).Wait();
                TaskDialog.Show("NexusTwin", $"Successfully synchronized {structuralElements.Count} elements.");
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                message = ex.Message;
                return Result.Failed;
            }
        }

        private async Task SyncWithNexusTwin(IEnumerable<Element> elements)
        {
            foreach (var el in elements)
            {
                var payload = new 
                {
                    element_id = el.UniqueId,
                    name = el.Name,
                    element_type = "COLUMN", // Simplified for demo
                    material_class = "concrete",
                    age_years = 0.0,
                    floor_level = "L1"
                };

                var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");
                _client.DefaultRequestHeaders.Clear();
                _client.DefaultRequestHeaders.Add("X-NexusTwin-API-Key", ApiKey);
                
                await _client.PostAsync(ApiUrl, content);
            }
        }
    }
}
