using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Collections;
using System.Diagnostics;
using System.Security.Cryptography;
using BepInEx;
using HarmonyLib;
using Newtonsoft.Json.Linq;
using UnityEngine;

[BepInPlugin("local.brickmcp.stability", "Brick MCP native stability", "0.1.0")]
public class StudioBridge : BaseUnityPlugin
{
    static StudioBridge service;
    string root, job, input;
    string checkerHash;
    JObject request, result;
    object awaiter, simulator;
    int phase, loadedFrames;
    DateTime started;
    float nextPoll;
    float nextStatus;
    const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static;

    static Type Find(string name)
    {
        return AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType(name, false)).FirstOrDefault(t => t != null);
    }
    static object Get(object obj, string name)
    {
        Type t = obj as Type ?? obj.GetType();
        PropertyInfo p = t.GetProperty(name, Flags);
        if (p != null) return p.GetValue(obj is Type ? null : obj, null);
        FieldInfo f = t.GetField(name, Flags);
        if (f == null) throw new MissingMemberException(t.FullName, name);
        return f.GetValue(obj is Type ? null : obj);
    }
    static object Call(object obj, string name, params object[] args)
    {
        return obj.GetType().GetMethods(Flags).Single(m => m.Name == name && m.GetParameters().Length == args.Length).Invoke(obj, args);
    }
    static string Hash(string path)
    {
        using (var sha = SHA256.Create()) using (var f = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(f)).Replace("-", "").ToLowerInvariant();
    }
    public static void CacheDirectory(ref string path)
    {
        path = Path.Combine(Paths.GameRootPath, "worker-profile");
        Directory.CreateDirectory(path);
    }
    void Awake()
    {
        service = this;
        var patches = new Harmony("local.brickmcp.worker-profile");
        patches.Patch(
            Find("Studio.Application.Configuration.Path.StudioPath+CachedApplicationDataDirectory").GetConstructor(new Type[] { typeof(string) }),
            new HarmonyMethod(typeof(StudioBridge), "CacheDirectory"));
        patches.Patch(Find("GameWorld").GetMethod("Update", Flags), null,
            new HarmonyMethod(typeof(StudioBridge), "NativeUpdate"));
        root = Path.GetFullPath(Path.Combine(Paths.GameRootPath, "jobs"));
        checkerHash = Hash(Find("StabilitySimulator").Assembly.Location);
        Directory.CreateDirectory(root);
        Application.runInBackground = true;
        File.WriteAllText(Path.Combine(root, "bridge.json"), JObject.FromObject(new {
            pid = Process.GetCurrentProcess().Id, unity = Application.unityVersion,
            bridge_version = "0.1.0", status = "starting"
        }).ToString());
        Logger.LogInfo("Native Studio bridge loaded; jobs=" + root);
    }
    void Finish(Exception error)
    {
        if (error != null)
        {
            result = JObject.FromObject(new { ok = false, error = error.ToString(), phase = phase });
            if (simulator != null) try { Call(simulator, "TerminateSimulation"); } catch { }
        }
        result["request_id"] = Path.GetFileNameWithoutExtension(job);
        result["elapsed_seconds"] = (DateTime.UtcNow - started).TotalSeconds;
        string output = job + ".result.json";
        File.WriteAllText(output + ".tmp", result.ToString());
        File.Move(output + ".tmp", output);
        phase = 0; job = null; awaiter = null;
    }
    void StartSimulation(int index)
    {
        object task = Call(simulator, "SimulateStability", index, null);
        awaiter = Call(task, "GetAwaiter");
    }
    JArray FlaggedParts()
    {
        var parts = new JArray();
        foreach (DictionaryEntry pair in (IDictionary)Get(simulator, "partToDEDic"))
        {
            int code = (int)Get(pair.Value, "ColorCodeForStabilityTest");
            if (code == 47) continue;
            Matrix4x4 m = (Matrix4x4)Get(pair.Key, "TransformMatrix");
            parts.Add(JObject.FromObject(new { part_number = (string)Get(pair.Key, "PartName"),
                x = m.m03, y = m.m13, z = -m.m23, test_color = code,
                rotation = new float[] {m.m00,m.m01,-m.m02,m.m10,m.m11,-m.m12,-m.m20,-m.m21,m.m22} }));
        }
        return parts;
    }
    JArray ConnectorPositions()
    {
        var parts = new JArray();
        foreach (DictionaryEntry pair in (IDictionary)Get(simulator, "partToDEDic"))
        {
            var connectors = new JArray();
            var list = Get(pair.Key, "CachedConnectivityList") as IEnumerable;
            if (list != null) foreach (object c in list)
            {
                Vector3 pos = (Vector3)Get(c, "Position");
                Vector3 dir = (Vector3)Get(c, "DirectionVector");
                connectors.Add(JObject.FromObject(new { type = Get(c, "ConnectivityType").ToString(),
                    subtype = (int)Get(c, "SubType"), length = (float)Get(c, "Length"),
                    position = new float[] { pos.x, pos.y, -pos.z },
                    direction = new float[] { dir.x, dir.y, -dir.z } }));
            }
            Matrix4x4 m = (Matrix4x4)Get(pair.Key, "TransformMatrix");
            parts.Add(JObject.FromObject(new {part_number=(string)Get(pair.Key,"PartName"), x=m.m03,y=m.m13,z=-m.m23, connectors=connectors}));
        }
        return parts;
    }
    JArray UnmodelledParts()
    {
        var parts = new JArray();
        foreach (DictionaryEntry pair in (IDictionary)Get(simulator, "partToDEDic"))
        {
            var list = Get(pair.Key, "CachedConnectivityList") as ICollection;
            if (list != null && list.Count > 0) continue;
            Matrix4x4 m = (Matrix4x4)Get(pair.Key, "TransformMatrix");
            parts.Add(JObject.FromObject(new {part_number=(string)Get(pair.Key,"PartName"),x=m.m03,y=m.m13,z=-m.m23,
                reason="No native Studio connector definitions"}));
        }
        return parts;
    }
    public static void NativeUpdate() { if (!object.ReferenceEquals(service, null)) service.Pump(); }
    void OnDestroy() { Logger.LogInfo("Bridge component destroyed; native Update hook remains active"); }
    void Pump()
    {
        try
        {
            Application.targetFrameRate = phase == 0 ? 5 : 60;
            Type wt = Find("GameWorld"), mt = Find("MenuHandler");
            object world = wt == null ? null : Get(wt, "Current"), menu = mt == null ? null : Get(mt, "Current");
            if (Time.realtimeSinceStartup > nextStatus)
            {
                nextStatus = Time.realtimeSinceStartup + 2f;
                File.WriteAllText(Path.Combine(root, "bridge.json"), JObject.FromObject(new {
                    pid = Process.GetCurrentProcess().Id, status = world != null && menu != null ? "ready" : "starting",
                    world_present = world != null, menu_present = menu != null, phase = phase,
                    heartbeat = DateTime.UtcNow.ToString("o") }).ToString());
            }
            if (world == null || menu == null) return;
            if (phase == 0)
            {
                if (Time.realtimeSinceStartup < nextPoll) return;
                nextPoll = Time.realtimeSinceStartup + 0.25f;
                string pending = Directory.GetFiles(root, "*.request.json").OrderBy(p => File.GetLastWriteTimeUtc(p)).FirstOrDefault();
                if (pending == null) return;
                job = pending.Substring(0, pending.Length - ".request.json".Length);
                File.Move(pending, job + ".active.json");
                started = DateTime.UtcNow;
                phase = 1;
                request = JObject.Parse(File.ReadAllText(job + ".active.json"));
                input = Path.GetFullPath((string)request["path"]);
                if (!input.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) || Path.GetExtension(input) != ".io")
                    throw new Exception("Audit input must be a .io inside the bridge jobs directory");
                if (Hash(input) != (string)request["sha256"]) throw new Exception("Input hash mismatch");
                simulator = Get(Find("StabilitySimulator"), "Instance");
                Call(simulator, "TerminateSimulation");
                Call(Get(world, "_fileLoadingService"), "OpenModelByPath", input, false, null, false);
                loadedFrames = 0;
                return;
            }
            if ((DateTime.UtcNow - started).TotalSeconds > 120) throw new TimeoutException("Studio operation timed out");
            if (phase == 1)
            {
                if ((bool)Get(world, "IsOnOpenOrLoadingModel")) { loadedFrames = 0; return; }
                object loadedFile = Get(Get(world, "_loadedFileService"), "LoadedFile");
                string loadedPath = (string)Get(loadedFile, "FilePath");
                IDictionary map = (IDictionary)Get(world, "LDrawPartToDrawableElementDic");
                if (map.Count != (int)request["expected_parts"]) return;
                if (++loadedFrames < 3) return;
                // The input may be treated as an imported/untitled file. Record the
                // native path and require the part count plus unique model name below.
                object active = Get(loadedFile, "ActiveModel");
                string modelName = (string)Get(active, "ModelName");
                if (modelName != Path.GetFileNameWithoutExtension((string)request["model_name"])) throw new Exception("Loaded model identity mismatch: " + modelName);
                result = JObject.FromObject(new { ok = true, source = "native_studio_runtime",
                    studio_assembly_sha256 = checkerHash,
                    audit_sha256 = Hash(input), parts_checked = map.Count,
                    loaded_path = loadedPath, model_name = modelName });
                result["coordinate_system"] = "LDraw_LDU";
                StartSimulation(0); phase = 2; return;
            }
            if (!(bool)Get(awaiter, "IsCompleted")) return;
            Call(awaiter, "GetResult");
            if (phase == 2)
            {
                result["warnings"] = (int)Get(simulator, "NumOfClutchPowerWarnings");
                result["cautions"] = (int)Get(simulator, "NumOfClutchPowerCautions");
                result["stability_issues"] = (int)Get(simulator, "NumOfStablityIssues");
                result["clutch_parts"] = FlaggedParts();
                StartSimulation(1); phase = 3; return;
            }
            result["detached_sections"] = (int)Get(simulator, "NumOfDetachedSections");
            result["detached_parts"] = FlaggedParts();
            result["unmodelled_parts"] = UnmodelledParts();
            if ((bool?)request["include_connectors"] == true) result["connector_parts"] = ConnectorPositions();
            Finish(null);
        }
        catch (Exception ex)
        {
            Logger.LogError(ex);
            if (job != null) Finish(ex);
        }
    }
}
