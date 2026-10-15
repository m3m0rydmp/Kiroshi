"""Small indexed asset summaries; raw evidence stays in the record store."""
import ipaddress
import json
from urllib.parse import urlsplit

from .traffic import response_status


class AssetMixin:
    def initialize_assets(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS asset_index (
            id TEXT PRIMARY KEY, engagement_id TEXT, value TEXT, host TEXT,
            asset_type TEXT, tool TEXT, status INTEGER, updated TEXT,
            identity TEXT, job_count INTEGER)""")
        for name, columns in (("engagement", "engagement_id,updated DESC,id"),
                              ("host", "engagement_id,host,value,id"),
                              ("type", "engagement_id,asset_type,tool"),
                              ("updated", "updated DESC,id")):
            self.db.execute(f"CREATE INDEX IF NOT EXISTS assets_{name} ON asset_index ({columns})")
        self.sync_asset_index()

    def index_asset(self, asset):
        value = str(asset.get("value", ""))
        try:
            host = str(ipaddress.ip_address(value))
        except ValueError:
            try:
                host = (urlsplit(value if "://" in value else "//" + value).hostname or "").lower().rstrip(".")
            except ValueError:
                host = ""
        category = "url" if "://" in value else "host"
        if category == "host":
            try:
                ipaddress.ip_address(host)
                category = "ip"
            except ValueError:
                pass
        detail = asset.get("detail")
        code = response_status(detail) if isinstance(detail, dict) else None
        self.db.execute("INSERT OR REPLACE INTO asset_index VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (asset["id"], asset.get("engagement_id"), value, host, category,
                         asset.get("tool", ""), code, asset.get("updated", asset.get("first_seen", "")),
                         asset.get("identity", "Anonymous"), len(asset.get("job_ids", []))))

    def sync_asset_index(self):
        # Also supports imported databases and externally seeded local fixtures.
        # Normal application writes maintain this index in the same transaction.
        with self.lock:
            source = self.db.execute("SELECT count(*) FROM records WHERE kind='asset'").fetchone()[0]
            indexed = self.db.execute("SELECT count(*) FROM asset_index").fetchone()[0]
            if source != indexed:
                self.db.execute("DELETE FROM asset_index WHERE id NOT IN (SELECT id FROM records WHERE kind='asset')")
                rows = self.db.execute("SELECT r.body FROM records r LEFT JOIN asset_index a ON a.id=r.id WHERE r.kind='asset' AND a.id IS NULL")
                for (body,) in rows.fetchall():
                    self.index_asset(json.loads(body))
            self.db.commit()

    def asset_overview(self):
        self.sync_asset_index()
        with self.lock:
            counts = dict(self.db.execute("SELECT engagement_id,count(*) FROM asset_index GROUP BY engagement_id"))
            rows = self.db.execute("SELECT id,engagement_id,value,host,asset_type,tool,status,updated,identity,job_count FROM asset_index ORDER BY updated DESC,id LIMIT 10").fetchall()
        return dict(total=sum(counts.values()), by_engagement=counts, preview=self.asset_rows(rows))

    @staticmethod
    def asset_rows(rows):
        columns = ("id", "engagement_id", "value", "host", "asset_type", "tool", "status", "updated", "identity", "job_count")
        return [dict(zip(columns, row)) for row in rows]

    def asset_page(self, params):
        self.sync_asset_index()
        limit = int(params.get("limit", 50))
        page = int(params.get("page", 1))
        if not 1 <= limit <= 200 or not 1 <= page <= 1000000:
            raise ValueError("Use pages of 1–200 assets and a positive page number")
        engagement = str(params.get("engagement_id", ""))
        query = str(params.get("q", "")).strip()
        host = str(params.get("host", "")).strip().lower().rstrip(".")
        category = str(params.get("type", ""))
        tool = str(params.get("tool", ""))
        status = str(params.get("status", ""))
        order = str(params.get("sort", "recent"))
        if len(query) > 200 or len(host) > 253 or len(tool) > 100:
            raise ValueError("Asset filter is too long")
        if category not in ("", "host", "url", "ip") or status not in ("", "2xx", "3xx", "4xx", "5xx", "none") or order not in ("recent", "host"):
            raise ValueError("Invalid asset filter")
        where, args = [], []
        for column, value in (("engagement_id", engagement), ("host", host), ("asset_type", category), ("tool", tool)):
            if value:
                where.append(column + "=?")
                args.append(value)
        if query:
            where.append("value LIKE ? ESCAPE '\\'")
            args.append("%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
        if status == "none":
            where.append("status IS NULL")
        elif status:
            where.append("status>=? AND status<?")
            args += [int(status[0]) * 100, (int(status[0]) + 1) * 100]
        clause = " WHERE " + " AND ".join(where) if where else ""
        sort = "updated DESC,id" if order == "recent" else "host,value,id"
        with self.lock:
            total = self.db.execute("SELECT count(*) FROM asset_index" + clause, args).fetchone()[0]
            pages = max(1, (total + limit - 1) // limit)
            page = min(page, pages)
            rows = self.db.execute("SELECT id,engagement_id,value,host,asset_type,tool,status,updated,identity,job_count FROM asset_index" + clause + " ORDER BY " + sort + " LIMIT ? OFFSET ?", [*args, limit, (page - 1) * limit]).fetchall()
            base = " WHERE engagement_id=?" if engagement else ""
            base_args = [engagement] if engagement else []
            types = dict(self.db.execute("SELECT asset_type,count(*) FROM asset_index" + base + " GROUP BY asset_type", base_args))
            sources = dict(self.db.execute("SELECT tool,count(*) FROM asset_index" + base + " GROUP BY tool", base_args))
            hosts = self.db.execute("SELECT host,count(*) FROM asset_index" + base + " GROUP BY host ORDER BY count(*) DESC,host LIMIT 100", base_args).fetchall()
        return dict(items=self.asset_rows(rows), total=total, page=page, pages=pages, limit=limit,
                    facets=dict(types=types, sources=sources, hosts=[dict(host=h, count=n) for h, n in hosts]))
