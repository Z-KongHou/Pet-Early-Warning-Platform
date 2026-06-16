package com.hamster.yingshi.controller;

import com.hamster.yingshi.common.Result;
import com.hamster.yingshi.utils.JwtUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Safe read-only SQL execution for the AI agent.
 *
 * <p><b>Hard security boundary:</b> user_id is forcibly injected by the backend.
 * The AI never writes its own user_id filter — any user_id clause in the AI's
 * SQL is stripped and replaced with the server-supplied value.</p>
 */
@RestController
@RequestMapping("/api/internal")
public class DatabaseQueryController {

    private static final Logger log = LoggerFactory.getLogger(DatabaseQueryController.class);

    // -- Safety constants --

    private static final Set<String> ALLOWED_TABLES = Set.of(
        "users", "hamsters", "cameras", "alerts", "messages",
        "activity_history", "pet_analysis", "pet_state", "frame_images", "settings"
    );

    private static final Set<String> MASKED_COLUMNS = Set.of(
        "password_hash", "access_token"
    );

    private static final List<String> SECRET_KEY_PATTERNS = List.of("api_key", "secret", "password");

    private static final List<String> FORBIDDEN_KEYWORDS = List.of(
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "UNION", "INTO OUTFILE",
        "INTO DUMPFILE", "LOAD_FILE", "LOAD DATA", "GRANT", "REVOKE",
        "SHUTDOWN", "RENAME", "REPLACE"
    );

    private static final int MAX_ROWS = 100;

    private static final Pattern TABLE_PATTERN =
        Pattern.compile("\\b(?:FROM|JOIN)\\s+`?(\\w+)`?", Pattern.CASE_INSENSITIVE);

    private static final Pattern WHERE_PATTERN =
        Pattern.compile("\\bWHERE\\b", Pattern.CASE_INSENSITIVE);

    private static final Pattern CLAUSE_BOUNDARY =
        Pattern.compile("\\b(ORDER\\s+BY|GROUP\\s+BY|LIMIT|HAVING)\\b", Pattern.CASE_INSENSITIVE);

    /** Strips any user_id = N the AI wrote (case-insensitive, with optional AND). */
    private static final Pattern USER_ID_FILTER =
        Pattern.compile("\\buser_id\\s*=\\s*\\d+\\s*(AND\\s*)?", Pattern.CASE_INSENSITIVE);

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private JwtUtils jwtUtils;

    // -- Endpoint --

    @PostMapping("/query")
    public Result<List<Map<String, Object>>> executeQuery(
            @RequestBody Map<String, Object> body,
            @RequestHeader(value = "Authorization", required = false) String authorization) {

        String sql = ((String) body.getOrDefault("sql", "")).trim();
        if (sql.isEmpty()) {
            return Result.error(400, "Missing 'sql' field");
        }

        // Extract user_id from JWT (backend is the single authority)
        int userId = 1; // default: dev/demo mode
        if (authorization != null && authorization.startsWith("Bearer ")) {
            String token = authorization.substring(7);
            try {
                if (jwtUtils.validateToken(token)) {
                    userId = jwtUtils.getUserIdFromToken(token);
                }
            } catch (Exception e) {
                log.warn("JWT validation failed, using default userId=1: {}", e.getMessage());
            }
        }

        // 1. Safety validation (table whitelist, keyword blacklist)
        String rejection = validateSql(sql);
        if (rejection != null) {
            log.warn("SQL rejected: {} — reason: {}", sql, rejection);
            return Result.error(403, rejection);
        }

        // 2. Force-inject user_id (strip what AI wrote, inject server value)
        sql = injectUserId(sql, userId);

        // 3. Wrap with row limit
        String safeSql = "SELECT * FROM (" + sql + ") AS _agent_subquery LIMIT " + MAX_ROWS;

        // 4. Execute
        List<Map<String, Object>> rows;
        try {
            rows = jdbcTemplate.queryForList(safeSql);
        } catch (Exception e) {
            log.error("SQL execution error: {} — sql: {}", e.getMessage(), safeSql);
            return Result.error(500, "Query execution failed: " + e.getMessage());
        }

        // 5. Mask sensitive columns
        rows = sanitizeResults(rows);

        log.info("SQL ok userId={}: {} row(s). sql: {}", userId, rows.size(),
            sql.length() > 150 ? sql.substring(0, 150) + "..." : sql);

        return Result.success(rows);
    }

    // -- Validation --

    private String validateSql(String sql) {
        String upper = sql.toUpperCase().trim();

        if (!upper.startsWith("SELECT")) {
            return "Only SELECT statements are allowed";
        }

        for (String kw : FORBIDDEN_KEYWORDS) {
            if (Pattern.compile("\\b" + kw + "\\b", Pattern.CASE_INSENSITIVE).matcher(sql).find()) {
                return "Forbidden SQL keyword: " + kw;
            }
        }

        Set<String> tables = extractTables(sql);
        if (tables.isEmpty()) {
            return "Could not identify any table in the query (FROM/JOIN required)";
        }
        for (String t : tables) {
            if (!ALLOWED_TABLES.contains(t.toLowerCase())) {
                return "Table not allowed: " + t + ". Allowed: " + ALLOWED_TABLES;
            }
        }

        return null;
    }

    private Set<String> extractTables(String sql) {
        Set<String> tables = new LinkedHashSet<>();
        Matcher m = TABLE_PATTERN.matcher(sql);
        while (m.find()) {
            tables.add(m.group(1));
        }
        return tables;
    }

    // -- user_id injection --

    /**
     * Force-injects the server-supplied {@code user_id} into the query.
     *
     * <ol>
     *   <li>Strips any {@code user_id = N} the AI wrote (untrusted input)</li>
     *   <li>Cleans up dangling {@code WHERE AND} / trailing {@code WHERE}</li>
     *   <li>Injects {@code table.user_id = ?} into the main WHERE clause,
     *       or adds a new WHERE clause before ORDER/GROUP/LIMIT/end</li>
     * </ol>
     */
    private String injectUserId(String sql, int userId) {
        // Strip any user_id filter the AI wrote
        sql = USER_ID_FILTER.matcher(sql).replaceAll("");
        // Clean artifacts: "WHERE AND" → "WHERE", "WHERE  " at end → remove
        sql = sql.replaceAll("(?i)WHERE\\s+AND\\s+", "WHERE ");
        sql = sql.replaceAll("(?i)WHERE\\s*$", "");

        String table = extractFirstTable(sql);
        if (table == null) {
            return sql; // shouldn't happen — validation already checked
        }
        String condition = table + ".user_id = " + userId;

        Matcher whereMatch = WHERE_PATTERN.matcher(sql);
        if (whereMatch.find()) {
            // Has WHERE → inject after the keyword
            int pos = whereMatch.end();
            sql = sql.substring(0, pos) + " " + condition + " AND " + sql.substring(pos).trim();
        } else {
            // No WHERE → insert before ORDER BY / GROUP BY / LIMIT / HAVING, or at end
            Matcher clauseMatch = CLAUSE_BOUNDARY.matcher(sql);
            if (clauseMatch.find()) {
                int pos = clauseMatch.start();
                sql = sql.substring(0, pos).trim() + " WHERE " + condition + " " + sql.substring(pos);
            } else {
                sql = sql.trim() + " WHERE " + condition;
            }
        }

        return sql;
    }

    private String extractFirstTable(String sql) {
        Matcher m = TABLE_PATTERN.matcher(sql);
        return m.find() ? m.group(1) : null;
    }

    // -- Result sanitization --

    private List<Map<String, Object>> sanitizeResults(List<Map<String, Object>> rows) {
        List<Map<String, Object>> clean = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Map<String, Object> out = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : row.entrySet()) {
                String col = entry.getKey();
                Object val = entry.getValue();

                if (MASKED_COLUMNS.contains(col)) {
                    out.put(col, "****");
                    continue;
                }
                if ("key_value".equals(col) && isSecretSetting(row)) {
                    out.put(col, "****");
                    continue;
                }

                out.put(col, val);
            }
            clean.add(out);
        }
        return clean;
    }

    private boolean isSecretSetting(Map<String, Object> row) {
        Object keyName = row.get("key_name");
        if (keyName == null) return false;
        String kn = keyName.toString().toLowerCase();
        for (String pattern : SECRET_KEY_PATTERNS) {
            if (kn.contains(pattern)) return true;
        }
        return false;
    }
}
