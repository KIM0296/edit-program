-- TASK-023 F1: reviewed one-shot read observations, no editing semantics.
print("FREE_F1|BOOT|START")

local allowlist = {
    GetProductName = true,
    GetVersionString = true,
    GetProjectManager = true,
    GetCurrentProject = true,
    GetCurrentTimeline = true,
    GetUniqueId = true,
    GetName = true,
    GetStartFrame = true,
    GetEndFrame = true,
    GetTrackCount = true,
    GetItemListInTrack = true,
    GetStart = true,
    GetEnd = true,
    GetDuration = true,
    GetMediaPoolItem = true,
    GetMediaId = true,
}

local function escape(value)
    return (string.gsub(value, "[%%|%c]", function(c)
        return string.format("%%%02X", string.byte(c))
    end))
end

local function raw_value(value, seen)
    local kind = type(value)
    if kind == "nil" then return "nil" end
    if kind == "string" then return "string:" .. string.format("%q", value) end
    if kind == "boolean" then return value and "boolean:true" or "boolean:false" end
    if kind == "number" then return "number:" .. string.format("%.17g", value) end
    if kind ~= "table" or getmetatable(value) ~= nil then return kind .. ":" .. "OPAQUE" end
    seen = seen or {}
    if seen[value] then error("CYCLIC_RAW_TABLE") end
    seen[value] = true
    local entries = {}
    for key, child in pairs(value) do
        if type(key) ~= "number" and type(key) ~= "string" and type(key) ~= "boolean" then
            error("OPAQUE_TABLE_KEY")
        end
        entries[#entries + 1] = raw_value(key, seen) .. "=" .. raw_value(child, seen)
    end
    table.sort(entries)
    seen[value] = nil
    return "table:{" .. table.concat(entries, ";") .. "}"
end

local function emit(subject, method, outcome, kind, raw, capability, mapping)
    print("FREE_F1|OBS|" .. escape(subject) .. "|" .. escape(method) .. "|" .. outcome
        .. "|" .. kind .. "|" .. escape(raw) .. "|" .. capability .. "|" .. mapping)
end

local function error_text(value)
    if type(value) == "string" then return value end
    local ok, text = pcall(function() return raw_value(value) end)
    if ok then return text end
    return "NONSTRING_ERROR:" .. type(value)
end

local function observe(subject, method, parent, lookup, operation, shape)
    if not allowlist[method] then error("UNDECLARED_READ") end
    if parent == nil then
        emit(subject, method, "UNKNOWN", "nil", "PARENT_NOT_OBSERVED", "UNKNOWN", "NOT_ESTABLISHED")
        return nil
    end
    local found, member = pcall(lookup)
    if not found then
        emit(subject, method, "ERROR", type(member), error_text(member), "UNKNOWN", "NOT_ESTABLISHED")
        return nil
    end
    if member == nil then
        emit(subject, method, "UNAVAILABLE", "nil", "nil", "UNAVAILABLE", "NOT_ESTABLISHED")
        return nil
    end
    if type(member) ~= "function" then
        local encoded_member, raw_member = pcall(function() return raw_value(member) end)
        emit(subject, method, "UNKNOWN", type(member), "NONCALLABLE" .. ":" ..
            (encoded_member and raw_member or error_text(raw_member)), "AVAILABLE_AMBIGUOUS", "NOT_ESTABLISHED")
        return nil
    end
    local ok, value = pcall(operation)
    if not ok then
        emit(subject, method, "ERROR", type(value), error_text(value), "UNKNOWN", "NOT_ESTABLISHED")
        return nil
    end
    local encoded, raw = pcall(function() return raw_value(value) end)
    if not encoded then
        emit(subject, method, "ERROR", type(value), "SERIALIZATION_ERROR" .. ":" .. error_text(raw), "UNKNOWN", "NOT_ESTABLISHED")
        return nil
    end
    if value == nil then
        emit(subject, method, "NIL", "nil", raw, "UNKNOWN", "NOT_ESTABLISHED")
        return nil
    end
    local typed = shape == "string" and type(value) == "string"
    if shape == "count" then
        typed = type(value) == "number" and value >= 0 and value < math.huge and value % 1 == 0
    end
    emit(subject, method, "VALUE", type(value), raw,
        typed and "AVAILABLE_TYPED" or "AVAILABLE_AMBIGUOUS", "RAW_ONLY")
    return value
end

local function inspect_item(item, path)
    observe(path, "GetUniqueId", item, function() return item.GetUniqueId end, function() return item:GetUniqueId() end, "string")
    observe(path, "GetName", item, function() return item.GetName end, function() return item:GetName() end, "string")
    observe(path, "GetStart", item, function() return item.GetStart end, function() return item:GetStart(false) end, "coordinate")
    observe(path, "GetEnd", item, function() return item.GetEnd end, function() return item:GetEnd(false) end, "coordinate")
    observe(path, "GetDuration", item, function() return item.GetDuration end, function() return item:GetDuration(false) end, "coordinate")
    local media = observe(path, "GetMediaPoolItem", item, function() return item.GetMediaPoolItem end, function() return item:GetMediaPoolItem() end, "handle")
    observe(path .. "/media", "GetUniqueId", media, function() return media.GetUniqueId end, function() return media:GetUniqueId() end, "string")
    observe(path .. "/media", "GetMediaId", media, function() return media.GetMediaId end, function() return media:GetMediaId() end, "string")
end

local function inspect_timeline(timeline)
    observe("timeline", "GetUniqueId", timeline, function() return timeline.GetUniqueId end, function() return timeline:GetUniqueId() end, "string")
    observe("timeline", "GetName", timeline, function() return timeline.GetName end, function() return timeline:GetName() end, "string")
    observe("timeline", "GetStartFrame", timeline, function() return timeline.GetStartFrame end, function() return timeline:GetStartFrame() end, "coordinate")
    observe("timeline", "GetEndFrame", timeline, function() return timeline.GetEndFrame end, function() return timeline:GetEndFrame() end, "coordinate")
    for _, track_type in ipairs({"video", "audio", "subtitle"}) do
        local path = "track/" .. track_type
        local count = observe(path, "GetTrackCount", timeline, function() return timeline.GetTrackCount end, function() return timeline:GetTrackCount(track_type) end, "count")
        if type(count) == "number" and count >= 0 and count < math.huge and count % 1 == 0 then
            for index = 1, count do
                -- These diagnostic paths are not native identities or chronological clip ranks.
                local track_path = path .. "/" .. string.format("%.17g", index)
                local items = observe(track_path, "GetItemListInTrack", timeline, function() return timeline.GetItemListInTrack end, function() return timeline:GetItemListInTrack(track_type, index) end, "collection")
                if type(items) == "table" then
                    local keys = {}
                    local valid = true
                    for key in pairs(items) do
                        if type(key) ~= "number" or key < 1 or key == math.huge or key % 1 ~= 0 then
                            valid = false
                        else
                            keys[#keys + 1] = key
                        end
                    end
                    if valid then
                        table.sort(keys)
                        for _, key in ipairs(keys) do
                            inspect_item(items[key], track_path .. "/entry/" .. string.format("%.17g", key))
                        end
                    else
                        emit(track_path, "ENUMERATION", "UNKNOWN", "table", "INVALID_ENUMERATION_KEYS", "AVAILABLE_AMBIGUOUS", "NOT_ESTABLISHED")
                    end
                end
            end
        end
    end
end

local function run()
    local global_resolve = resolve
    emit("root", "GLOBAL_RESOLVE", global_resolve == nil and "NIL" or "VALUE",
        type(global_resolve), global_resolve == nil and "nil" or "OPAQUE", "UNKNOWN", "NOT_ESTABLISHED")
    observe("runtime", "GetProductName", global_resolve, function() return global_resolve.GetProductName end, function() return global_resolve:GetProductName() end, "string")
    observe("runtime", "GetVersionString", global_resolve, function() return global_resolve.GetVersionString end, function() return global_resolve:GetVersionString() end, "string")
    local manager = observe("runtime", "GetProjectManager", global_resolve, function() return global_resolve.GetProjectManager end, function() return global_resolve:GetProjectManager() end, "handle")
    local project = observe("project", "GetCurrentProject", manager, function() return manager.GetCurrentProject end, function() return manager:GetCurrentProject() end, "handle")
    observe("project", "GetUniqueId", project, function() return project.GetUniqueId end, function() return project:GetUniqueId() end, "string")
    local timeline = observe("timeline", "GetCurrentTimeline", project, function() return project.GetCurrentTimeline end, function() return project:GetCurrentTimeline() end, "handle")
    inspect_timeline(timeline)
end

local ok, failure = pcall(run)
if not ok then
    emit("probe", "RUN", "ERROR", type(failure), error_text(failure), "UNKNOWN", "NOT_ESTABLISHED")
end
print(ok and "FREE_F1|END|COMPLETE_READ_ATTEMPT" or "FREE_F1|END|ERROR")
