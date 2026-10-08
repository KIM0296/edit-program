-- TASK-023 Free Resolve read-only canary.
-- No mutation, file IO, network IO, eval, dynamic code, or generic method dispatch.

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

local ok_root, resolve_or_error = pcall(function()
    if app == nil or type(app.GetResolve) ~= "function" then
        return nil
    end
    return app:GetResolve()
end)

if not ok_root then
    emit("ROOT", "ERROR:" .. tostring(resolve_or_error))
    return
end

local resolve = resolve_or_error
if resolve == nil then
    emit("ROOT", "NONE")
    return
end

emit("ROOT", "CONNECTED")
call("PRODUCT", resolve, "GetProductName")
call("VERSION_STRING", resolve, "GetVersionString")

local manager = call("PROJECT_MANAGER", resolve, "GetProjectManager")
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
