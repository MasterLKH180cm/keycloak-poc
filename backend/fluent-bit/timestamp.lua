-- Add timestamp if not present
function add_timestamp(tag, timestamp, record)
    new_record = record
    if record["@timestamp"] == nil then
        new_record["@timestamp"] = os.date("!%Y-%m-%dT%H:%M:%S") .. "." .. string.format("%03d", math.floor((timestamp % 1) * 1000)) .. "Z"
    end
    return 1, timestamp, new_record
end
