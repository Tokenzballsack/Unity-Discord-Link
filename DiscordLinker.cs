using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Networking;
using TMPro;

/// <summary>
/// Attach to a Canvas GameObject that contains the linking UI.
/// Assign the TMP text fields in the Inspector.
/// </summary>
public class DiscordLinker : MonoBehaviour
{
    [Header("API")]
    [Tooltip("Base URL of your FastAPI server, e.g. https://yourserver.com")]
    public string apiBaseUrl = "http://localhost:8000";

    [Header("UI References")]
    public TextMeshProUGUI codeText;        // Shows the 8-char code
    public TextMeshProUGUI statusLabelText; // Shows MEMBER / VIP / etc.
    public TextMeshProUGUI instructionText; // Guidance text
    public GameObject      linkingPanel;    // Panel shown before linking
    public GameObject      linkedPanel;     // Panel shown after linking

    [Header("Polling")]
    [Tooltip("How often (seconds) to check if the player has linked / status changed")]
    public float pollInterval = 5f;

    // ── Internal ──────────────────────────────────────────────────────────────
    private string _gamePlayerId;
    private bool   _isLinked = false;

    // ─────────────────────────────────────────────────────────────────────────

    void Start()
    {
        // Use a stable unique ID for this player.
        // Replace this with your own auth ID (Steam, account ID, etc.)
        _gamePlayerId = GetOrCreatePlayerId();

        StartCoroutine(InitialiseLinker());
    }

    // ── Step 1: Get/generate the link code ───────────────────────────────────

    IEnumerator InitialiseLinker()
    {
        string url = $"{apiBaseUrl}/generate-code";
        var payload = JsonUtility.ToJson(new GenerateCodeRequest { game_player_id = _gamePlayerId });

        using var req = new UnityWebRequest(url, "POST");
        req.uploadHandler   = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(payload));
        req.downloadHandler = new DownloadHandlerBuffer();
        req.SetRequestHeader("Content-Type", "application/json");

        yield return req.SendWebRequest();

        if (req.result == UnityWebRequest.Result.Success)
        {
            var response = JsonUtility.FromJson<GenerateCodeResponse>(req.downloadHandler.text);
            ShowCode(response.code);
            StartCoroutine(PollStatus());
        }
        else
        {
            Debug.LogError($"[DiscordLinker] Failed to get code: {req.error}");
            if (instructionText) instructionText.text = "Could not reach server. Check your connection.";
        }
    }

    // ── Step 2: Show the code panel ──────────────────────────────────────────

    void ShowCode(string code)
    {
        if (linkingPanel) linkingPanel.SetActive(true);
        if (linkedPanel)  linkedPanel.SetActive(false);

        if (codeText)
        {
            codeText.text = code;
            // Style it so it's easy to read
            codeText.fontSize         = 36;
            codeText.fontStyle        = FontStyles.Bold;
            codeText.characterSpacing = 6;
        }

        if (instructionText)
            instructionText.text = "Go to our Discord and run:\n/link " + code;
    }

    // ── Step 3: Poll for link + status changes ───────────────────────────────

    IEnumerator PollStatus()
    {
        while (true)
        {
            yield return new WaitForSeconds(pollInterval);
            yield return StartCoroutine(FetchStatus());
        }
    }

    IEnumerator FetchStatus()
    {
        string url = $"{apiBaseUrl}/player-status/{_gamePlayerId}";

        using var req = UnityWebRequest.Get(url);
        yield return req.SendWebRequest();

        if (req.result != UnityWebRequest.Result.Success)
        {
            Debug.LogWarning($"[DiscordLinker] Poll failed: {req.error}");
            yield break;
        }

        var status = JsonUtility.FromJson<PlayerStatusResponse>(req.downloadHandler.text);

        if (status.linked)
            ApplyLinkedState(status);
        else if (!_isLinked && instructionText)
            instructionText.text = "Waiting for you to link in Discord…";
    }

    // ── Step 4: Update UI once linked ────────────────────────────────────────

    void ApplyLinkedState(PlayerStatusResponse status)
    {
        _isLinked = true;

        if (linkingPanel) linkingPanel.SetActive(false);
        if (linkedPanel)  linkedPanel.SetActive(true);

        if (statusLabelText)
        {
            statusLabelText.text = status.label;

            if (ColorUtility.TryParseHtmlString(status.colour, out Color c))
                statusLabelText.color = c;
            else
                statusLabelText.color = Color.grey;
        }
    }

    // ── Persistent player ID ─────────────────────────────────────────────────

    static string GetOrCreatePlayerId()
    {
        const string key = "DiscordLinker_PlayerId";
        if (!PlayerPrefs.HasKey(key))
            PlayerPrefs.SetString(key, Guid.NewGuid().ToString());
        return PlayerPrefs.GetString(key);
    }

    // ── JSON models ──────────────────────────────────────────────────────────

    [Serializable] class GenerateCodeRequest  { public string game_player_id; }
    [Serializable] class GenerateCodeResponse { public string code; }

    [Serializable]
    class PlayerStatusResponse
    {
        public bool   linked;
        public string label;
        public string colour;
        public string discord_name;
    }
}
