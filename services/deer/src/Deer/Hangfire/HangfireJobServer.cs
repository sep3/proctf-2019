using System;
using Hangfire;

namespace Deer.Hangfire
{
    public class HangfireJobServer : IDisposable
    {
        private readonly BackgroundJobServer _server;

        public HangfireJobServer(JobStorage storage)
        {
            _server = new BackgroundJobServer(storage);
        }

        public void Dispose()
        {
            _server?.Dispose();
        }
    }
}