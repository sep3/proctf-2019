using System;
using System.Threading.Tasks;
using Deer.Messages;
using Elasticsearch.Net;
using Nest;

namespace LogProcessor
{
    public class LogRepository : ILogRepository
    {
        private ElasticClient _elasticClient;

        public LogRepository(Uri elasticSearchUri)
        {
            var userInfo = elasticSearchUri.UserInfo.Split(':');
            var user = userInfo[0];
            var password = userInfo[1];

            var nestSettings = new ConnectionSettings(elasticSearchUri)
                .BasicAuthentication(user, password)
                // TODO change to AuthorityIsRoot
                .ServerCertificateValidationCallback(CertificateValidations.AllowAll);
            
            _elasticClient = new ElasticClient(nestSettings);
        }

        public async Task IndexAsync(string userName, LogData logData)
        {
            var doc = new LogData();
            // TODO how to set type
            await _elasticClient.IndexAsync(doc, id => id.Index(userName));
        }
    }
}