# Icon catalog conventions

The icon index at `~/.cache/azure-icons/index.json` exposes:

- `icons` — every canonical name (kebab-case) → `{path, display}`.
- `synonyms` — friendly aliases → canonical name.

The renderer resolves a spec's `type` value by:
1. Looking it up directly in `icons` (canonical match).
2. Falling back to `synonyms`.
3. Trying `name.rstrip("s")`, `f"azure-{name}"`, and `name + "s"` heuristics.
4. Drawing a labeled yellow placeholder if nothing matches.

## Naming convention

Microsoft's filenames are like `10035-icon-service-App-Services.svg`. The bootstrap script strips the numeric prefix and `icon-service-` segment, lowercases, replaces spaces with `-`, and drops non-alphanumeric chars. So `App Services` → `app-services` (plural — MS chose the plural here even though the user-facing brand is "App Service"). The skill ships pre-populated synonyms for the common singular/plural mismatches so you usually don't need to think about it.

## Common gotchas

| Canonical name | Common alternatives that work |
|---|---|
| `app-services` | `app-service`, `azure-app-service`, `webapp`, `web-app` |
| `function-apps` | `function`, `functions`, `function-app`, `azure-functions` |
| `kubernetes-services` | `aks`, `kubernetes`, `k8s` |
| `sql-database` | `sql`, `azure-sql`, `sqldb`, `azuresql` |
| `azure-cosmos-db` | `cosmos`, `cosmosdb`, `cosmos-db` |
| `storage-accounts` | `storage`, `blob`, `blob-storage` |
| `key-vaults` | `key-vault`, `keyvault`, `kv` |
| `azure-service-bus` | `service-bus`, `sb`, `azuresb` |
| `event-hubs` | `event-hub`, `eventhub` |
| `event-grid-domains` | `event-grid`, `eventgrid` |
| `cache-redis` | `redis`, `azure-cache-redis` |
| `private-endpoints` | `private-endpoint`, `pe` |
| `front-door-and-cdn-profiles` | `front-door`, `frontdoor`, `afd` |
| `application-gateways` | `application-gateway`, `app-gateway`, `agw` |
| `virtual-networks` | `vnet`, `virtual-network` |
| `network-security-groups` | `nsg` |
| `firewalls` | `firewall`, `azure-firewall` |
| `bastions` | `bastion` |
| `application-insights` | `app-insights`, `appins` |
| `log-analytics-workspaces` | `log-analytics` |
| `microsoft-entra-id` | `entra`, `aad`, `azure-ad` |
| `azure-openai` | `openai` |
| `ai-studio` | `ai-foundry`, `azure-ai-foundry`, `foundry`, `azure-ai-studio` |
| `container-apps-environments` | `container-app`, `container-apps` |
| `container-instances` | `aci`, `container-instance` |
| `container-registries` | `acr`, `container-registry` |

## When in doubt

```bash
python3 ~/.claude/skills/azure-svg-diagram/scripts/icon_index.py search <keyword>
python3 ~/.claude/skills/azure-svg-diagram/scripts/icon_index.py resolve <name>
```

Search is a substring match over canonical name + display name, so `search log` shows every Log-related icon, `search ai` shows the AI/ML ones, etc.

## Adding synonyms

To make a new alias permanent, edit `EXTRA_SYNONYMS` in `scripts/bootstrap_icons.py` and re-run `bootstrap_icons.py --refresh`. The synonyms dictionary is regenerated each time the bootstrap script runs.
