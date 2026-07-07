import { useEffect, useState } from "react";
import "./App.css";

interface Team {
  slug: string;
  city: string;
  full_name: string;
  abbrev: string;
}

interface Player {
  id: string;
  first_name: string;
  last_name: string;
  main_team_slug: string | null;
}

const API_BASE = "/api";

function App() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/teams`)
      .then((r) => r.json())
      .then(setTeams);
    fetch(`${API_BASE}/players`)
      .then((r) => r.json())
      .then(setPlayers);
  }, []);

  async function assignPlayer(playerId: string, teamSlug: string | null) {
    const url = teamSlug
      ? `${API_BASE}/players/${playerId}/team/${teamSlug}`
      : `${API_BASE}/players/${playerId}/team/none`;
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: teamSlug ? "assign" : "remove" }),
    });
    const updated = await fetch(`${API_BASE}/players`).then((r) => r.json());
    setPlayers(updated);
  }

  async function exportRoster(teamSlug: string) {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/teams/${teamSlug}/export`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${teamSlug}-roster.bin`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="App">
      <h1>NHL Legacy Fantasy</h1>

      <section>
        <h2>Teams</h2>
        <ul className="team-list">
          {teams.map((team) => (
            <li key={team.slug}>
              <span>
                {team.city} {team.full_name.replace(team.city, "").trim()} ({team.abbrev})
              </span>
              <div>
                <button onClick={() => setSelectedTeam(team.slug)}>Roster</button>
                <button disabled={loading} onClick={() => exportRoster(team.slug)}>
                  Export .bin
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {selectedTeam && (
        <section>
          <h2>
            Roster: {teams.find((t) => t.slug === selectedTeam)?.full_name}
          </h2>
          <ul className="player-list">
            {players
              .filter((p) => p.main_team_slug === selectedTeam)
              .map((player) => (
                <li key={player.id}>
                  <span>
                    {player.first_name} {player.last_name}
                  </span>
                  <button onClick={() => assignPlayer(player.id, null)}>Remove</button>
                </li>
              ))}
          </ul>

          <h3>Unassigned players</h3>
          <ul className="player-list">
            {players
              .filter((p) => p.main_team_slug !== selectedTeam)
              .map((player) => (
                <li key={player.id}>
                  <span>
                    {player.first_name} {player.last_name}
                    {player.main_team_slug
                      ? ` (${teams.find((t) => t.slug === player.main_team_slug)?.abbrev})`
                      : " (FA)"}
                  </span>
                  <button onClick={() => assignPlayer(player.id, selectedTeam)}>
                    Assign
                  </button>
                </li>
              ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default App;
