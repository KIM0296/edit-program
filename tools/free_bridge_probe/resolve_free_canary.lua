-- TASK-023 Free Resolve read-only canary.
-- No mutation, file IO, network IO, eval, dynamic code, or generic method dispatch.

print("FREE_CANARY|BOOT|START")

local function emit(key, value)
    local text = tostring(value)
    text = string.gsub(text, "[\r\n]", " ")
    print("FREE_CANARY|" .. key .. "|" .. text)
end

local function call(label, object, method)
    if object == nil then
        emit(label, "NONE")
        return nil
    end
    local fn = object[method]
    if type(fn) ~= "function" then
        emit(label, "UNAVAILABLE")
        return nil
    end
    local ok, value = pcall(fn, object)
    if not ok then
        emit(label, "ERROR:" .. tostring(value))
        return nil
    end
    if value == nil then
        emit(label, "NONE")
    else
        emit(label, value)
    end
    return value
end

local resolve_instance = nil

if resolve ~= nil then
    resolve_instance = resolve
    emit("ROOT_SOURCE", "GLOBAL_RESOLVE")
elseif app ~= nil and type(app.GetResolve) == "function" then
    local ok, value = pcall(function()
        return app:GetResolve()
    end)
    if ok then
        resolve_instance = value
        emit("ROOT_SOURCE", "APP_GETRESOLVE")
    else
        emit("ROOT_SOURCE", "APP_GETRESOLVE_ERROR")
        emit("ROOT_ERROR", tostring(value))
    end
else
    emit("ROOT_SOURCE", "NONE")
end

if resolve_instance == nil then
    emit("ROOT", "NONE")
    return
end

emit("ROOT", "CONNECTED")
call("PRODUCT", resolve_instance, "GetProductName")
call("VERSION_STRING", resolve_instance, "GetVersionString")

local manager = call("PROJECT_MANAGER", resolve_instance, "GetProjectManager")
if manager == nil then
    return
end

local database = call("DATABASE", manager, "GetCurrentDatabase")
if type(database) == "table" then
    emit("DATABASE_TYPE", database.DbType or "MISSING")
    emit("DATABASE_NAME", database.DbName or "MISSING")
end

local project = call("PROJECT", manager, "GetCurrentProject")
if project == nil then
    return
end

call("PROJECT_NAME", project, "GetName")
call("PROJECT_ID", project, "GetUniqueId")

local timeline = call("TIMELINE", project, "GetCurrentTimeline")
if timeline == nil then
    return
end

call("TIMELINE_NAME", timeline, "GetName")
call("TIMELINE_ID", timeline, "GetUniqueId")
call("TIMELINE_START", timeline, "GetStartFrame")
call("TIMELINE_END", timeline, "GetEndFrame")
