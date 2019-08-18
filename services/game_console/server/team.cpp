#include "team.h"
#include "checksystem.h"
#include <stdio.h>
#include <string.h>


static const uint32_t kFlagIdLen = 8;
static const uint32_t kFlagLen = 32;
static const uint32_t kRecordSize = kFlagIdLen + kFlagLen;


void Team::LoadDb()
{
    char filename[256];
    sprintf(filename, "data/%s.dat", desc.name.c_str());

    bool error = false;
    storage = fopen(filename, "r+");
	if(storage)
	{
		fseek(storage, 0, SEEK_END);
		size_t fileSize = ftell(storage);
		fseek(storage, 0, SEEK_SET);

        if((fileSize % kRecordSize) == 0)
        {
            uint32_t recordsNum = fileSize / kRecordSize;
            for(uint32_t i = 0; i < recordsNum; i++)
            {
                char flagId[kFlagIdLen + 1];
                memset(flagId, 0, sizeof(flagId));
				if(fread(flagId, kFlagIdLen, 1, storage) != 1)
                {
                    error = true;
                    printf("Failed to read storage %s\n", filename);
                    break;
                }

                char flag[kFlagLen + 1];
                memset(flag, 0, sizeof(flag));
				if(fread(flag, kFlagLen, 1, storage) != 1)
                {
                    error = true;
                    printf("Failed to read storage %s\n", filename);
                    break;
                }

                flags.insert({flagId, flag});
            }
        }
        else
        {
            printf("Storage corrupted %s\n", filename);
            error = true;
        }

        printf("Storage has been read succefully %s\n", filename);
    }
    else
    {
        printf("Storage does not exists %s\n", filename);
        error = true;
    }

    if(error)
	{
		FILE* c = fopen(filename, "w");
		fclose(c);
		storage = fopen(filename, "r+");
	}
}


User* Team::AddUser(const std::string& name, const std::string& password)
{
    std::lock_guard<std::mutex> guard(mutex);
    User* user = new User();
    user->name = name;
    user->password = password;
    user->ipAddr = ~0u;
    users[user->name] = user;
    return user;
}


User* Team::GetUser(const std::string& name)
{
    std::lock_guard<std::mutex> guard(mutex);
    auto iter = users.find(name);
    if(iter == users.end())
        return nullptr;
    return iter->second;
}


User* Team::GetUser(IPAddr ipAddr)
{
    std::lock_guard<std::mutex> guard(mutex);
    for(auto& u : users)
    {
        if(u.second->ipAddr == ipAddr)
            return u.second;
    }
    return nullptr;
}


bool Team::AuthorizeUser(const std::string& name, const std::string& password)
{
    std::lock_guard<std::mutex> guard(mutex);
    auto iter = users.find(name);
    if(iter == users.end())
        return false;
    return iter->second->password == password;
}


void Team::AddNotification(Notification* n, const std::string& except)
{
    std::lock_guard<std::mutex> guard(mutex);
    for(auto& iter : users)
    {
        if(iter.first == except)
            continue;
        iter.second->AddNotification(n);
    }
}


void Team::Update()
{
    std::lock_guard<std::mutex> guard(mutex);
    for(auto& iter : users)
        iter.second->Update();
}


void Team::DumpStats(std::string& out)
{
    std::lock_guard<std::mutex> guard(mutex);

    char buf[512];
    sprintf(buf, "Team%u %s:\n", desc.number, desc.name.c_str());
    out.append(buf);

    sprintf(buf, "  Network: %s\n", inet_ntoa(desc.network));
    out.append(buf);

    sprintf(buf, "  Last time team post notification: %f\n", lastTimeTeamPostNotification);
    out.append(buf);

    sprintf(buf, "  Number of flags: %u\n", (uint32_t)flags.size());
    out.append(buf);

    IPAddr hwConsoleIp = GetHwConsoleIp(desc.network);
    sprintf(buf, "  HW Console IP: %s\n\n", inet_ntoa(hwConsoleIp));
    out.append(buf);

    for(auto& iter : users)
    {
        auto& u = iter.second;

        sprintf(buf, "  User %s:\n", iter.first.c_str());
        out.append(buf);

        sprintf(buf, "    Password: %s\n", u->password.c_str());
        out.append(buf);

        sprintf(buf, "    IP: %s\n", inet_ntoa(u->ipAddr));
        out.append(buf);

        bool isHw = u->ipAddr == hwConsoleIp;
        sprintf(buf, "    Is HW: %s\n", isHw ? "yes" : "no");
        out.append(buf);

        sprintf(buf, "    Notifications in queue: %u\n", u->GetNotificationsInQueue());
        out.append(buf);

        sprintf(buf, "    Last user notify time: %f\n", u->lastUserNotifyTime);
        out.append(buf);

        sprintf(buf, "    Auth key: %x\n\n", u->authKey);
        out.append(buf);
    }
}

void Team::PutFlag(const char* flagId, const char* flag)
{
    std::lock_guard<std::mutex> guard(mutex);

    if(strlen(flagId) != kFlagIdLen || strlen(flag) != kFlagLen)
    {
        printf("CRITICAL ERROR: Invalid length of flag id or flag: %s %s\n", flagId, flag);
        exit(1);
    }

    uint32_t offset = flags.size() * kRecordSize;
    fseek(storage, offset, SEEK_SET);
    fwrite(flagId, kFlagIdLen, 1, storage);
    fwrite(flag, kFlagLen, 1, storage);
    fflush(storage);

    flags.insert({flagId, flag});
}

const char* Team::GetFlag(const char* flagId)
{
    std::lock_guard<std::mutex> guard(mutex);
    auto iter = flags.find(flagId);
    if(iter == flags.end())
        return nullptr;
    return iter->second.c_str();
}